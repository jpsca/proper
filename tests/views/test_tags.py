"""
Custom block tags: `{% name args %}body{% endname %}` calls the catalog's
function for `name` with the body as a function, `caller`, that renders it
only if called. What fragment caching needs.
"""

import subprocess

import pytest
from markupsafe import Markup

from proper.views import Catalog, CompileError, ComponentNotCompiledError
from .helpers import BIN, load_module, run_jxc


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


def record(*args, caller, template, **kwargs):
    """A tag that shows what it received."""
    return Markup(f"[{args!r} {sorted(kwargs.items())!r} {template}: {caller()}]")


def skip(*args, caller, template, **kwargs):
    """A tag that never renders its body."""
    return "skipped"


class Cache:
    """A fragment cache: the body is rendered only on a miss."""

    def __init__(self):
        self.store = {}

    def __call__(self, key, *, caller, template, expires_in=None):
        full_key = (template, key)
        if full_key not in self.store:
            self.store[full_key] = caller()
        return self.store[full_key]


def counter():
    calls = []

    def count():
        calls.append(1)
        return len(calls)

    return calls, count


# Syntax


@pytest.mark.parametrize("tag, expected", [
    ("{% record 1, 'a', b=2 %}x{% endrecord %}", "[(1, 'a') [('b', 2)] page.jx: x]"),
    ("{% record(1, 'a', b=2) %}x{% endrecord %}", "[(1, 'a') [('b', 2)] page.jx: x]"),
    ("{% record (1, 'a') %}x{% endrecord %}", "[((1, 'a'),) [] page.jx: x]"),
    ("{% record %}x{% endrecord %}", "[() [] page.jx: x]"),
    ("{% record() %}x{% endrecord %}", "[() [] page.jx: x]"),
    ("{% record v ~ '!', *[3], **{'k': v} %}x{% endrecord %}", "[('<v>!', 3) [('k', '<v>')] page.jx: x]"),
    ("a {%- record -%} x {%- endrecord -%} b", "a[() [] page.jx: x]b"),
])
def test_arguments(tmp_path, tag, expected):
    write(tmp_path, {"page.jx": "{# def v #}" + tag})
    catalog = Catalog(tmp_path, tags={"record": record}, autoescape=False)
    assert catalog.render("page.jx", v="<v>") == expected


def test_template_is_the_path_in_its_folder(tmp_path):
    write(tmp_path, {
        "pages/users/show.html.jx": '{# import "../../card.jx" as Card #}<Card />{% record %}{% endrecord %}',
        "card.jx": "{% record %}{% endrecord %}",
    })
    html = Catalog(tmp_path, tags={"record": record}).render("pages/users/show.html.jx")
    assert html == "[() [] card.jx: ][() [] pages/users/show.html.jx: ]"


def test_the_body_is_rendered_only_if_called(tmp_path):
    calls, count = counter()
    write(tmp_path, {"page.jx": "{% skip %}{{ count() }}{% endskip %}"})
    catalog = Catalog(tmp_path, tags={"skip": skip}, count=count)
    assert catalog.render("page.jx") == "skipped"
    assert calls == []


def test_fragment_cache(tmp_path):
    calls, count = counter()
    write(tmp_path, {
        "page.jx": "{# def items #}{% for i in items %}{% cache i %}<b>{{ i }}:{{ count() }}</b>{% endcache %}{% endfor %}",
        "other.jx": "{% cache 1 %}<i>{{ count() }}</i>{% endcache %}",
    })
    catalog = Catalog(tmp_path, tags={"cache": Cache()}, count=count)
    assert catalog.render("page.jx", items=[1, 2]) == "<b>1:1</b><b>2:2</b>"
    assert catalog.render("page.jx", items=[1, 2, 3]) == "<b>1:1</b><b>2:2</b><b>3:3</b>"
    # same key in another template: another fragment
    assert catalog.render("other.jx") == "<i>4</i>"
    assert len(calls) == 4


def test_nested_tags_and_blocks(tmp_path):
    write(tmp_path, {
        "box.jx": "<div>{% slot s %}{% endslot %}{{ content }}</div>",
        "page.jx": """{# import "box.jx" as Box #}{# def items #}
{%- for i in items -%}
{% cache "outer" ~ i %}<Box>{% fill s %}{% cache "inner" ~ i %}{{ loop.index }}{% endcache %}{% endfill %}{{ i }}</Box>{% endcache %}
{%- endfor %}""",
    })
    catalog = Catalog(tmp_path, tags={"cache": Cache()})
    assert catalog.render("page.jx", items=["a", "b"]) == "<div>1a</div><div>2b</div>"


# Escaping


def test_body_is_markup_with_autoescape(tmp_path):
    write(tmp_path, {"page.jx": "{# def v #}{% cache 1 %}<b>{{ v }}</b>{% endcache %}"})
    catalog = Catalog(tmp_path, tags={"cache": Cache()})
    html = catalog.render("page.jx", v="<v>")
    assert html == "<b>&lt;v&gt;</b>"
    # from the cache too
    assert catalog.render("page.jx", v="other") == "<b>&lt;v&gt;</b>"


def test_the_result_is_not_escaped(tmp_path):
    """As the block tags of Jinja extensions: the function decides."""
    write(tmp_path, {"page.jx": "{% skip %}{% endskip %}", "mail.txt.jx": "{% skip %}{% endskip %}"})
    catalog = Catalog(tmp_path, tags={"skip": lambda *, caller, template: "<b>"})
    assert catalog.render("page.jx") == "<b>"
    assert catalog.render("mail.txt.jx") == "<b>"


# Scope: the body of a tag, like a fill, is a function of its own


def test_set_in_the_body_reads_the_outer_value_first(tmp_path):
    write(tmp_path, {
        "page.jx": "{% set x = 1 %}{% record %}{{ x }}{% set x = x + 1 %}{{ x }}{% endrecord %}{{ x }}",
    })
    html = Catalog(tmp_path, tags={"record": record}, autoescape=False).render("page.jx")
    assert html == "[() [] page.jx: 12]1"


def test_for_target_in_the_body_shadows_an_outer_name(tmp_path):
    write(tmp_path, {
        "page.jx": "{# def i #}{% record %}{{ i }}{% for i in [7, 8] if i > 7 %}{{ i }}{% endfor %}{{ i }}{% endrecord %}",
    })
    html = Catalog(tmp_path, tags={"record": record}, autoescape=False).render("page.jx", i=0)
    assert html == "[() [] page.jx: 080]"


def test_set_in_a_fill_reads_the_outer_value_first(project):
    """It raised UnboundLocalError: the fill is a Python function, and the
    `set` made `x` local to all of it."""
    project.write({
        "box.jx": "{% slot s %}{% endslot %}",
        "page.jx": (
            '{# import "box.jx" as Box #}{% set x = 1 %}'
            "<Box>{% fill s %}{{ x }}{% set x = 2 %}{{ x }}{% endfill %}</Box>{{ x }}"
        ),
    })
    project.assert_same("page.jx")


def test_for_target_in_a_fill_shadows_an_outer_name(project):
    project.write({
        "box.jx": "{% slot s %}{% endslot %}",
        "page.jx": (
            '{# import "box.jx" as Box #}{# def n #}'
            "<Box>{% fill s %}{{ n }}{% for n in [1, 2] %}{{ n }}{% endfor %}{% endfill %}</Box>"
        ),
    })
    project.assert_same("page.jx", n=0)


def test_set_in_a_recursive_loop_reads_the_outer_value_first(project):
    project.write({
        "page.jx": (
            "{# def tree #}{% set d = 'x' %}"
            "{% for n in tree recursive %}{{ d }}{% set d = n.k %}{{ d }}{{ loop(n.c) }}{% endfor %}{{ d }}"
        ),
    })
    project.assert_same("page.jx", tree=[{"k": "a", "c": [{"k": "b", "c": []}]}])


# The module and the catalog


def test_module_declares_its_tags(tmp_path):
    write(tmp_path, {"page.jx": "x"})
    assert run_jxc("--tags=zeta,cache", tmp_path).returncode == 0
    assert load_module(tmp_path / "page.py").TAGS == ("cache", "zeta")


def test_rendered_without_the_function(tmp_path):
    write(tmp_path, {"page.jx": "{% cache 1 %}x{% endcache %}"})
    assert run_jxc("--tags=cache", tmp_path).returncode == 0
    with pytest.raises(KeyError, match=r"No function for the tag \{% cache %\}"):
        load_module(tmp_path / "page.py").render()


def test_module_compiled_with_other_tags_is_recompiled(tmp_path):
    write(tmp_path, {"page.jx": "{% cache 1 %}x{% endcache %}"})
    assert run_jxc(tmp_path).returncode == 1  # `cache` is not a tag there
    assert run_jxc("--tags=cache,other", tmp_path).returncode == 0
    catalog = Catalog(tmp_path, compiler=BIN, tags={"cache": Cache()})
    assert catalog.render("page.jx") == "x"
    assert load_module(tmp_path / "page.py").TAGS == ("cache",)


def test_module_compiled_with_other_tags_without_compiler(tmp_path):
    write(tmp_path, {"page.jx": "x"})
    assert run_jxc(tmp_path).returncode == 0
    catalog = Catalog(tmp_path, compiler=False, auto_reload=False, tags={"cache": Cache()})
    with pytest.raises(ComponentNotCompiledError, match=r"compiled with the tags \(\)"):
        catalog.render("page.jx")


@pytest.mark.parametrize("name, why", [
    ("if", "a builtin statement"),
    ("macro", "a builtin statement"),
    ("endthing", "it starts with `end`"),
    ("2x", "not a valid name"),
    ("a-b", "not a valid name"),
])
def test_names_that_cannot_be_tags(tmp_path, name, why):
    with pytest.raises(ValueError, match=f"cannot be a tag: {why}"):
        Catalog(tmp_path, tags={name: record})
    result = subprocess.run([str(BIN), f"--tags={name}", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert f"`{name}` cannot be a tag: {why}" in result.stderr


def test_tag_function_must_be_callable(tmp_path):
    with pytest.raises(TypeError, match="not callable"):
        Catalog(tmp_path, tags={"cache": "nope"})


# Errors


@pytest.mark.parametrize("source, error", [
    ("{% cache 1 %}x", "page.jx:1:1: Unclosed block: expected `{% endcache %}`"),
    ("x{% endcache %}", "page.jx:1:2: Unexpected `{% endcache %}`"),
    ("{% other 1 %}x{% endother %}", "page.jx:1:1: Unknown statement `{% other %}`"),
    ("{% cache a b %}x{% endcache %}", "page.jx:1:12:"),
    ("{% cache(a) b %}x{% endcache %}", "page.jx:1:13:"),
])
def test_compile_errors(tmp_path, source, error):
    write(tmp_path, {"page.jx": source})
    catalog = Catalog(tmp_path, tags={"cache": Cache()})
    with pytest.raises(CompileError) as exc:
        catalog.compile()
    assert error in str(exc.value)
