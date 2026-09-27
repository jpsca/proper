"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import jinja2
from jinja2.compiler import CodeGenerator

from proper.jx import Catalog
from proper.jx.codegen import SAFE_FILTER, JxCodeGenerator


XSS = '<script>alert("x")</script>'
ESCAPED = "&lt;script&gt;"


def test_component_output_is_not_escaped(folder):
    """The whole point: a child's HTML reaches the parent as markup."""
    (folder / "child.jx").write_text("<em>hi</em>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    catalog = Catalog(folder, auto_reload=False)

    assert "<div><em>hi</em></div>" in catalog.render("parent.jx")


def test_prop_containing_html_is_still_escaped(folder):
    """
    Skipping `escape()` on the component call must not skip it on the values
    that component prints. This is the line between markup and data.
    """
    (folder / "child.jx").write_text("{# def text: str #}\n<em>{{ text }}</em>")
    (folder / "parent.jx").write_text(
        '{# def evil: str #}\n{# import "child.jx" as Child #}\n<Child text={{ evil }} />'
    )

    catalog = Catalog(folder, auto_reload=False)
    html = catalog.render("parent.jx", evil=XSS)

    assert ESCAPED in html
    assert "<script>" not in html


def test_slot_fill_escapes_its_values(folder):
    (folder / "card.jx").write_text("<div>{% slot body %}none{% endslot %}</div>")
    (folder / "page.jx").write_text(
        '{# def evil: str #}\n{# import "card.jx" as Card #}\n'
        "<Card>{% fill body %}{{ evil }}{% endfill %}</Card>"
    )

    catalog = Catalog(folder, auto_reload=False)
    html = catalog.render("page.jx", evil=XSS)

    assert ESCAPED in html
    assert "<script>" not in html


def test_slot_default_escapes_its_values(folder):
    (folder / "card.jx").write_text(
        "{# def evil: str #}\n<div>{% slot body %}{{ evil }}{% endslot %}</div>"
    )

    catalog = Catalog(folder, auto_reload=False)
    html = catalog.render("card.jx", evil=XSS)

    assert ESCAPED in html
    assert "<script>" not in html


def test_content_is_still_escaped(folder):
    """`{{ content }}` is written by hand, so it is not marked and still escapes."""
    (folder / "card.jx").write_text("<div>{{ content }}</div>")

    catalog = Catalog(folder, auto_reload=False)
    html = catalog.render("card.jx", content=XSS)

    assert ESCAPED in html
    assert "<script>" not in html


def test_attrs_render_is_still_escaped(folder):
    (folder / "card.jx").write_text("<div {{ attrs.render() }}>x</div>")

    catalog = Catalog(folder, auto_reload=False)
    html = catalog.render("card.jx", title=XSS)

    assert "<script>" not in html


def test_generator_is_installed_by_default(folder):
    catalog = Catalog(folder)

    assert catalog.jinja_env.code_generator_class is JxCodeGenerator
    assert catalog.jinja_env.filters[SAFE_FILTER] is not None


def test_foreign_code_generator_is_left_alone(folder):
    """
    An environment that brought its own generator keeps it, and the marker
    falls back to the identity filter — same output, one extra call.
    """
    class Custom(CodeGenerator):
        pass

    (folder / "child.jx").write_text("<em>hi</em>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    env = jinja2.Environment(autoescape=True)
    env.code_generator_class = Custom
    catalog = Catalog(folder, jinja_env=env, auto_reload=False)

    assert catalog.jinja_env.code_generator_class is Custom
    assert "<div><em>hi</em></div>" in catalog.render("parent.jx")


def test_marker_is_correct_without_autoescape(folder):
    (folder / "child.jx").write_text("<em>hi</em>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    env = jinja2.Environment(autoescape=False)
    catalog = Catalog(folder, jinja_env=env, auto_reload=False)

    assert "<div><em>hi</em></div>" in catalog.render("parent.jx")


def test_finalize_still_runs_on_marked_output(folder):
    """
    A configured `finalize` has to see every value. Marked expressions keep
    their wrapper so it is called.
    """
    seen = []

    def finalize(value):
        seen.append(value)
        return value

    (folder / "child.jx").write_text("<em>hi</em>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    env = jinja2.Environment(autoescape=True, finalize=finalize)
    catalog = Catalog(folder, jinja_env=env, auto_reload=False)
    html = catalog.render("parent.jx")

    assert "<div><em>hi</em></div>" in html
    assert any("<em>hi</em>" in str(v) for v in seen)
