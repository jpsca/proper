"""
Tracebacks of a failed render point to the templates: file, line, the
columns of the expression, and the template's variables as locals.
"""

import traceback
from pathlib import Path

import pytest

from proper.views import Catalog


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


def failure(catalog, name, **kwargs):
    with pytest.raises(Exception) as info:
        catalog.render(name, **kwargs)
    return info.value


def frames(exc):
    """(file name, line, function, first column, end column) of each frame."""
    return [
        (Path(f.filename).name, f.lineno, f.name, f.colno, f.end_colno)
        for f in traceback.extract_tb(exc.__traceback__)
    ]


def template_frames(exc):
    return [f for f in frames(exc) if f[0].endswith(".jx")]


class User:
    name = "Ann"


def test_the_expression_that_failed(tmp_path):
    write(tmp_path, {"page.jx": "{# def user #}\n<h1>Hi</h1>\n<p>{{ user.name }} and {{ user.nme }}</p>\n"})
    exc = failure(Catalog(tmp_path), "page.jx", user=User())
    assert isinstance(exc, AttributeError)
    assert template_frames(exc) == [("page.jx", 3, "template", 26, 34)]
    text = "".join(traceback.format_exception(exc))
    assert "    <p>{{ user.name }} and {{ user.nme }}</p>\n" + " " * 30 + "^" * 8 + "\n" in text


def test_columns_are_bytes_but_carets_are_characters(tmp_path):
    write(tmp_path, {"page.jx": "{# def user #}\n<p>ñandú → {{ user.nme }}</p>"})
    exc = failure(Catalog(tmp_path), "page.jx", user=User())
    text = "".join(traceback.format_exception(exc))
    line = "<p>ñandú → {{ user.nme }}</p>"
    carets = " " * (4 + line.index("user.nme")) + "^" * len("user.nme") + "\n"
    assert f"    {line}\n{carets}" in text


def test_components_macros_fills_tags_and_loops(tmp_path):
    write(tmp_path, {
        "card.jx": "{# def title #}\n<div>\n  {% slot head %}{% endslot %}\n</div>",
        "page.jx": """{# import "card.jx" as Card #}{# def items #}
{% macro row(item) -%}
  <td>{{ item.price * 2 }}</td>
{%- endmacro %}
<Card title="t">
  {% fill head %}
    {% cache 1 %}
      {% for it in items recursive %}{{ row(it) }}{{ loop(it.children) }}{% endfor %}
    {% endcache %}
  {% endfill %}
</Card>""",
    })
    catalog = Catalog(tmp_path, tags={"cache": lambda key, *, caller, template: caller()})
    items = [{"price": 1, "children": [{"price": None, "children": []}]}]
    exc = failure(catalog, "page.jx", items=items)
    assert isinstance(exc, TypeError)
    names = [(f[0], f[1], f[2]) for f in template_frames(exc)]
    assert names == [
        ("page.jx", 5, "template"),   # <Card
        ("card.jx", 3, "template"),   # its slot
        ("page.jx", 7, "fill"),       # the tag in the fill
        ("page.jx", 8, "tag"),        # the loop in the tag
        ("page.jx", 8, "loop"),       # the recursive call
        ("page.jx", 8, "loop"),
        ("page.jx", 3, "row"),        # the macro
    ]


def test_locals_are_the_templates_variables(tmp_path):
    write(tmp_path, {"page.jx": "{# def items #}{% set n = 2 %}{% for it in items %}{{ it.x * n }}{% endfor %}"})
    exc = failure(Catalog(tmp_path), "page.jx", items=[{"x": None}])
    tb = exc.__traceback__
    while tb.tb_next is not None:
        tb = tb.tb_next
    assert tb.tb_frame.f_code.co_filename.endswith("page.jx")
    variables = dict(tb.tb_frame.f_locals)
    assert variables == {"items": [{"x": None}], "content": "", "n": 2, "it": {"x": None}}


def test_minijx_frames_are_hidden(tmp_path):
    write(tmp_path, {"page.jx": "{# def user #}{{ user.nme }}"})
    exc = failure(Catalog(tmp_path), "page.jx", user=User())
    files = [f[0] for f in frames(exc)]
    assert "runtime.py" not in files  # where getattr_ raised
    assert files[-1] == "page.jx"


def test_user_code_frames_are_kept(tmp_path):
    def shout(value):
        raise ValueError("no")

    write(tmp_path, {"page.jx": "{# def v #}\n{{ v | shout }}"})
    exc = failure(Catalog(tmp_path, filters={"shout": shout}), "page.jx", v="x")
    assert [f[:3] for f in frames(exc)[-2:]] == [
        ("page.jx", 2, "template"),
        ("test_debug.py", shout.__code__.co_firstlineno + 1, "shout"),
    ]


def test_a_statement_points_to_its_expression(tmp_path):
    write(tmp_path, {"page.jx": "{# def x #}\n  {% set y = x.nope %}\n"})
    exc = failure(Catalog(tmp_path), "page.jx", x=1)
    assert template_frames(exc) == [("page.jx", 2, "template", 9, 19)]


def test_a_line_without_columns_has_no_carets(tmp_path):
    write(tmp_path, {
        "box.jx": "{% slot s %}{% endslot %}",
        "page.jx": '{# import "box.jx" as Box #}\n<Box>{% fill s %}\n{{ 1 / 0 }}{% endfill %}</Box>',
    })
    exc = failure(Catalog(tmp_path), "page.jx")
    box = [f for f in template_frames(exc) if f[0] == "box.jx"]
    # the slot: the whole line, so Python shows it without carets
    assert box == [("box.jx", 1, "template", 0, len("{% slot s %}{% endslot %}"))]
    text = "".join(traceback.format_exception(exc))
    assert "    {% slot s %}{% endslot %}\n  File" in text


def test_an_undefined_name(tmp_path):
    write(tmp_path, {
        "box.jx": "{% slot s %}{% endslot %}",
        "page.jx": '{# import "box.jx" as Box #}\n{{ nope }}',
        "fill.jx": '{# import "box.jx" as Box #}<Box>{% fill s %}{{ nope }}{% endfill %}</Box>',
    })
    catalog = Catalog(tmp_path)
    exc = failure(catalog, "page.jx")
    assert isinstance(exc, KeyError)
    assert exc.__notes__ == [
        "`nope` is not defined: it is not an argument of page.jx, a variable set in it, "
        "nor a global of the catalog"
    ]
    assert "of fill.jx" in failure(catalog, "fill.jx").__notes__[0]


def test_a_missing_argument_names_the_component(tmp_path):
    """Only when rendering: with `attrs=`, the compiler cannot tell."""
    write(tmp_path, {
        "ui/card.jx": "{# def title #}{{ title }}",
        "page.jx": '{# import "ui/card.jx" as Card #}\n<section>\n  <Card attrs={{ {} }} />\n</section>',
    })
    exc = failure(Catalog(tmp_path), "page.jx")
    assert str(exc) == "<ui/card.jx> missing 1 required keyword-only argument: 'title'"
    assert template_frames(exc) == [("page.jx", 3, "template", 2, 7)]


def test_a_render_inside_a_render(tmp_path):
    write(tmp_path, {"inner.jx": "{# def u #}\n{{ u.nme }}", "outer.jx": "{{ render('inner.jx', u=u) }}"})
    catalog = Catalog(tmp_path)
    catalog.globals["render"] = catalog.render
    catalog.globals["u"] = User()
    exc = failure(catalog, "outer.jx")
    assert [f[:2] for f in template_frames(exc)] == [("outer.jx", 1), ("inner.jx", 2)]


def test_without_the_template_file(tmp_path):
    """Deployed without the `.jx`: the file and line are still right."""
    views, out = tmp_path / "views", tmp_path / "build"
    write(views, {"page.jx": "{# def user #}\n{{ user.nme }}"})
    Catalog(views, output=out).compile()
    (views / "page.jx").unlink()
    catalog = Catalog(views, output=out, compiler=False, auto_reload=False)
    exc = failure(catalog, "page.jx", user=User())
    assert [f[:2] for f in template_frames(exc)] == [("page.jx", 2)]


def test_errors_outside_a_render_are_not_touched(tmp_path):
    from proper.views import ComponentNotFoundError

    with pytest.raises(ComponentNotFoundError):
        Catalog(tmp_path).render("nope.jx")


# The lookup, with a hand-made LINEMAP


def test_find_entry_fallbacks():
    from proper.views.debug import _find_entry

    module = {"LINEMAP": (
        (10, -1, -1, 0, 1, 0, 3),
        (12, 5, 9, 0, 2, 0, 4),
        (12, 20, 30, 0, 2, 10, 14),
    )}
    assert _find_entry(module, 12, 25, 1)[5] == 10       # the span with the column
    assert _find_entry(module, 12, 15, 1)[5] == 0        # between spans: the first one
    assert _find_entry(module, 11, None, 1)[4] == 1      # no entry: the closest above
    assert _find_entry(module, 9, None, 5) is None       # nothing above, in the function
    assert "__minijx_lineindex__" in module


def test_a_module_without_valid_sources_keeps_its_frames(tmp_path):
    write(tmp_path, {"page.jx": "{# def user #}{{ user.nme }}"})
    catalog = Catalog(tmp_path)
    catalog.compile()
    py = tmp_path / "page.py"
    py.write_text(py.read_text().replace("SOURCES = ('page.jx', )", "SOURCES = ()"))
    exc = failure(Catalog(tmp_path, compiler=False), "page.jx", user=User())
    assert template_frames(exc) == []
    assert frames(exc)[-2][0] == "page.py"   # the compiled code, as it was


def test_the_component_of_a_nested_line_without_entries():
    from types import SimpleNamespace

    from proper.views.debug import _component_at

    frame = SimpleNamespace(f_lineno=3, f_code=SimpleNamespace(co_firstlineno=3))
    assert _component_at(frame, {"LINEMAP": (), "COMPONENTS": {}}) is None


def test_a_module_without_a_linemap_keeps_its_frames(tmp_path):
    import re

    write(tmp_path, {"page.jx": "{# def user #}{{ user.nme }}"})
    Catalog(tmp_path).compile()
    py = tmp_path / "page.py"
    py.write_text(re.sub(r"LINEMAP = \(.*?\n\)", "LINEMAP = ()", py.read_text(), flags=re.S))
    exc = failure(Catalog(tmp_path, compiler=False), "page.jx", user=User())
    assert template_frames(exc) == []
