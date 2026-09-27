"""
Jx | Copyright (c) Juan-Pablo Scaletti

Regressions for the slot mechanism.

Before native slots, `Component.render` invoked the caller once per slot
*declared by the child* and used `body != content` to guess whether the caller
had actually filled it. Every test here pins down a behavior that heuristic
got wrong.
"""

import pytest

from proper.jx import Catalog


@pytest.fixture()
def counter():
    return {}


@pytest.fixture()
def tick(counter):
    def _tick(what: str) -> str:
        counter[what] = counter.get(what, 0) + 1
        return ""

    return _tick


def test_empty_fill_is_not_the_default(folder):
    """An intentionally empty fill must render empty, not fall back to the default."""
    (folder / "card.jx").write_text(
        "{# def #}<b>{% slot header %}DEFAULT{% endslot %}</b>"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}<Card>{% fill header %}{% endfill %}x</Card>'
    )
    cat = Catalog(folder)
    assert cat.render("page.jx").strip() == "<b></b>"


def test_fill_identical_to_content_is_kept(folder):
    """A fill that happens to render like the content must still be used."""
    (folder / "card.jx").write_text(
        "{# def #}H=[{% slot header %}DEFAULT{% endslot %}] C=[{{ content }}]"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}<Card>{% fill header %}SAME{% endfill %}SAME</Card>'
    )
    cat = Catalog(folder)
    assert cat.render("page.jx").strip() == "H=[SAME] C=[SAME]"


def test_nondeterministic_content_does_not_leak_into_slots(folder):
    """
    Content that renders differently each time must not be mistaken for a fill.

    `_get_random_id()` is a documented Jx helper, so this is not a corner case.
    """
    (folder / "card.jx").write_text(
        "{# def #}a=[{% slot a %}DEF-A{% endslot %}]"
        "b=[{% slot b %}DEF-B{% endslot %}]"
        "c=[{{ content }}]"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}<Card>{{ _get_random_id() }}</Card>'
    )
    cat = Catalog(folder)
    html = cat.render("page.jx").strip()

    assert html.startswith("a=[DEF-A]b=[DEF-B]c=[id-")
    assert html.count("id-") == 1, f"the content leaked into the slots: {html}"


def test_side_effecting_helper_in_content_runs_once(folder, counter, tick):
    """Three declared slots, none filled: the content must still render once."""
    (folder / "card.jx").write_text(
        "{# def #}{% slot a %}A{% endslot %}{% slot b %}B{% endslot %}"
        "{% slot c %}C{% endslot %}[{{ content }}]"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}<Card>{{ tick("content") }}</Card>'
    )
    cat = Catalog(folder, tick=tick)
    cat.render("page.jx")
    assert counter == {"content": 1}


def test_bodies_render_exactly_once(folder, counter, tick):
    """Three declared slots, one filled: one render of the content, one of the fill."""
    (folder / "card.jx").write_text(
        "{# def #}"
        "H:{% slot header %}DEF-H{% endslot %} "
        "B:{% slot body %}DEF-B{% endslot %} "
        "F:{% slot footer %}DEF-F{% endslot %} "
        "C:{{ content }}"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}'
        "<Card>"
        '{% fill header %}MY-HEADER{{ tick("fill:header") }}{% endfill %}'
        'MAIN{{ tick("body:main") }}'
        "</Card>"
    )
    cat = Catalog(folder, tick=tick)
    html = cat.render("page.jx").strip()

    assert html == "H:MY-HEADER B:DEF-B F:DEF-F C:MAIN"
    assert counter == {"body:main": 1, "fill:header": 1}


def test_fill_is_lazy(folder, counter, tick):
    """A fill whose slot is never reached must not be rendered at all."""
    (folder / "card.jx").write_text(
        "{# def #}{% if false %}{% slot header %}DEF-H{% endslot %}{% endif %}ok"
    )
    (folder / "page.jx").write_text(
        '{# import "card.jx" as Card #}'
        '<Card>{% fill header %}{{ tick("fill:header") }}{% endfill %}</Card>'
    )
    cat = Catalog(folder, tick=tick)
    assert cat.render("page.jx").strip() == "ok"
    assert counter == {}


def test_fill_inside_a_for_loop(folder):
    """Each fill must capture the loop variable of the frame where it is written."""
    (folder / "card.jx").write_text(
        "{# def #}[{% slot header %}DEF{% endslot %}]"
    )
    (folder / "page.jx").write_text(
        '{# def items: list #}'
        '{# import "card.jx" as Card #}'
        "{% for item in items %}"
        "<Card>{% fill header %}{{ item }}-{{ loop.index }}{% endfill %}</Card>"
        "{% endfor %}"
    )
    cat = Catalog(folder)
    html = cat.render("page.jx", items=["a", "b", "c"]).strip()
    assert html == "[a-1][b-2][c-3]"
