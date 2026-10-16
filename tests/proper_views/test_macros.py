"""
`{% macro %}`: same output as Jx (Jinja), with and without autoescape.
`caller`, `varargs` and `kwargs` are not supported.
"""

import pytest
from markupsafe import Markup

from proper.views import Catalog, CompileError


@pytest.mark.parametrize("source, kwargs", [
    # the shape of the forms in Proper's guides
    (
        """{# def items, label #}
{% macro render_item(item, label) -%}
<div>
  <label>{{ label }}</label>
  <input value="{{ item }}">
</div>
{%- endmacro %}
{% for item in items %}
  {{ render_item(item, label) }}
{% endfor %}
<template>{{ render_item("", label) }}</template>""",
        {"items": ["a", "<b>"], "label": "Name & <co>"},
    ),
    ("{% macro m(a, b=2) %}{{ a }}{{ b }}{% endmacro %}{{ m(1) }}|{{ m(1, 3) }}|{{ m(b=5, a=1) }}", {}),
    ("{% macro m(a, b=a ~ '!') %}{{ b }}{% endmacro %}{{ m('<x>') }}", {}),
    ("{% set s = 'S' %}{% macro m(a=s) %}{{ a }}{% endmacro %}{% set s = 'T' %}{{ m() }}", {}),
    ("{% set s = 'S' %}{% macro m() %}{{ s }}{% endmacro %}{% set s = 'T' %}{{ m() }}", {}),
    ("{% macro f(n) %}{{ n }}{% if n %}{{ f(n - 1) }}{% endif %}{% endmacro %}{{ f(3) }}", {}),
    ("{% macro m(x) %}<b>{{ x }}</b>{% endmacro %}{{ m('<a>') | upper }}{{ m(v) }}", {"v": Markup("<i>")}),
    ("{% set x = 1 %}{% macro m() %}{{ x }}{% set x = 2 %}{{ x }}{% endmacro %}{{ m() }}{{ x }}", {}),
    ("{% for i in [1, 2] %}{% macro m() %}{{ loop.index }}{{ i }}{% endmacro %}{{ m() }}{% endfor %}", {}),
    ("a {%- macro m() -%} x {%- endmacro -%} b{{ m() }}", {}),
    ("{% macro m(n) %}{% for i in range(n) %}{{ i }}{% endfor %}{% endmacro %}{{ m(3) }}{{ m(2) }}", {}),
    ("{% macro a() %}[{{ b() }}]{% endmacro %}{% macro b() %}b{% endmacro %}{{ a() }}", {}),
    ("{% macro m(v) %}{{ v }}{% endmacro %}{% set r = m('<x>') %}{{ r }}{{ r ~ '<y>' }}", {}),
    ("{% macro m() %}{{ 'x' | shout }}{% endmacro %}{{ m() }}", {}),
])
def test_same_as_jx(project, source, kwargs):
    names = ", ".join(sorted(kwargs))
    header = "" if source.startswith("{# def") or not names else f"{{# def {names} #}}"
    project.write({"page.jx": header + source})
    project.assert_same("page.jx", filters={"shout": lambda s: s.upper() + "!"}, **kwargs)


def test_macro_in_a_component_with_fills_and_content(project):
    project.write({
        "box.jx": "<div>{% slot head %}{% endslot %}{{ content }}</div>",
        "page.jx": """{# import "box.jx" as Box #}{# def form #}
{% macro field(form, name) %}<p>{{ name }}: {{ form[name] }}</p>{% endmacro %}
<Box>{% fill head %}{{ field(form, "title") }}{% endfill %}{{ field(form, "body") }}</Box>""",
    })
    project.assert_same("page.jx", form={"title": "<T>", "body": "B"})


def test_parameter_named_like_an_argument(project):
    """`form` is the component's argument and the macro's parameter."""
    project.write({
        "page.jx": """{# def form #}{% macro show(form) %}[{{ form }}]{% endmacro %}{{ show("inner") }}{{ form }}""",
    })
    project.assert_same("page.jx", form="outer")


def test_missing_argument_is_an_error(tmp_path):
    (tmp_path / "page.jx").write_text("{% macro m(a, b) %}{{ a }}{{ b }}{% endmacro %}{{ m(1) }}")
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'b'"):
        Catalog(tmp_path).render("page.jx")


@pytest.mark.parametrize("source, error", [
    ("{% macro %}x{% endmacro %}", "1:1: `{% macro %}` needs a name"),
    ("{% macro m %}x{% endmacro %}", "1:11: Expected `(` after the name of the macro"),
    ("{% macro m() %}x", "1:1: Unclosed block: expected `{% endmacro %}`"),
    ("x{% endmacro %}", "1:2: Unexpected `{% endmacro %}`"),
    ("{% macro m(a=1, b) %}{% endmacro %}", "1:17: A parameter without a default cannot follow one with a default"),
    ("{% macro m(a, a) %}{% endmacro %}", "Duplicate parameter `a`"),
    ("{% macro m(a.b) %}{% endmacro %}", "A macro parameter is a name"),
    ("{% macro m(*a) %}{% endmacro %}", "do not take `*args` or `**kwargs`"),
    ("{% macro m() %}{{ caller() }}{% endmacro %}", "1:19: `caller` is not supported in minijx macros"),
    ("{% macro m() %}{{ varargs }}{% endmacro %}", "`varargs` is not supported in minijx macros"),
    ("{% macro m() %}{{ kwargs }}{% endmacro %}", "`kwargs` is not supported in minijx macros"),
    ("{% macro class() %}{% endmacro %}", "`class` cannot be the name of a macro"),
    ("{% macro m(x) %}{% endmacro %}x{% endmacro %}", "Unexpected `{% endmacro %}`"),
])
def test_compile_errors(tmp_path, source, error):
    (tmp_path / "page.jx").write_text(source)
    with pytest.raises(CompileError) as exc:
        Catalog(tmp_path).compile()
    assert error in str(exc.value)


def test_caller_as_a_parameter_or_outside_a_macro(tmp_path):
    """Only a free `caller` inside a macro is refused."""
    (tmp_path / "page.jx").write_text(
        "{% macro m(caller) %}{{ caller }}{% endmacro %}{{ m(1) }}{{ caller }}"
    )
    assert Catalog(tmp_path, caller="g").render("page.jx") == "1g"
