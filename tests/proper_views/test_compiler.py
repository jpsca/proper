"""
Compiler behaviour that is not about rendered output: error reporting, the
docs templates from Jx, and what the binary refuses.
"""

import re

import pytest

from .helpers import JX_VIEWS, run_minijx


ERROR_RE = re.compile(r"^(.+?):(\d+):(\d+): (.+)$", re.MULTILINE)


def compile_error(project, source: str, name="a.jx"):
    project.write({name: source})
    result = project.compile()
    assert result.returncode == 1, result.stderr
    m = ERROR_RE.search(result.stderr)
    assert m, result.stderr
    assert m.group(1).endswith(name)
    assert not (project.mini / (name[:-3] + ".py")).exists()
    return int(m.group(2)), int(m.group(3)), m.group(4)


@pytest.mark.parametrize(
    "source,line,col,fragment",
    [
        ("<p>\n{{ 1 + }}</p>", 2, 8, "end of expression"),
        ("{% if x %}\n<p>", 1, 1, "endif"),
        ("<Card />", 1, 1, "not imported"),
        ('{# import "nope.jx" as Nope #}', 1, 1, "Cannot find"),
        ("{% for x in %}{% endfor %}", 1, 12, "Unexpected"),
        ("{% extends 'x' %}", 1, 1, "not supported"),
        ("{% include 'x' %}", 1, 1, "not supported"),
        ("{% call fn() %}x{% endcall %}", 1, 1, "`{% call %}` is not supported"),
        ("x{% endcall %}", 1, 2, "`{% endcall %}` is not supported"),
        ("{# def x=foo #}", 1, 10, "Use of foo not allowed"),
        ('{# import "b.jx" as B #}<B a="1" a="2" />', 1, 34, "Duplicate attribute `a` on `B`"),
        ('{# import "b.jx" as B #}<B data-id="1" data_id="2" />', 1, 40, "Duplicate attribute `data_id`"),
        ('{# def x="a".upper() #}', 1, 14, "Use of upper not allowed"),
        ("{% set a, b = 1, 2 %}", 1, 9, "only supports"),
        ("{% set x %}y{% endset %}", 1, 1, "only supports"),
        ("{% fill x %}{% endfill %}", 1, 1, "fill"),
        ("{{ x | }}", 1, 8, "filter name"),
        ("<p>{{ (1 + 2 }}</p>", 1, 14, "Expected `)`"),
        ("{{ [1, {'a': (2 }} }}", 1, 17, "Expected `)`"),
        ("{{ 'unclosed }}", 1, 1, "Unclosed `{{`"),
        ('<Card title="x"', 1, 1, "Unclosed"),
        ('{# import "@ui/x.jx" as X #}', 1, 1, "Prefixed imports"),
        ("{# def a b #}", 1, 10, "Unexpected"),
        ("{# def title #}\n{# def x #}", 2, 1, "Duplicate"),
        ("{% def title %}", 1, 1, "write `{# def ... #}`"),
        ('{% import "b.jx" as B %}', 1, 1, "write `{# import ... #}`"),
        ('<p></p>{# import "b.jx" as B #}<B />', 1, 32, "not imported"),
    ],
)
def test_errors_have_position(project, source, line, col, fragment):
    got_line, got_col, msg = compile_error(project, source)
    assert (got_line, got_col) == (line, col), msg
    assert fragment in msg


def test_error_inside_imported_component_names_that_file(project):
    project.write({"a.jx": '{# import "b.jx" as B #}<B />', "b.jx": "{{ 1 + }}"})
    result = project.compile()
    assert result.returncode == 1
    assert "b.jx:1:8" in result.stderr
    assert not (project.mini / "a.py").exists()


def test_other_files_still_compile_after_an_error(project):
    project.write({"bad.jx": "{{ }}", "good.jx": "ok"})
    result = project.compile()
    assert result.returncode == 1
    assert (project.mini / "good.py").exists()
    assert "1 file(s) written, 1 failed" in result.stderr


def test_usage_without_arguments():
    result = run_minijx()
    assert result.returncode == 2
    assert "usage" in result.stderr


def test_absolute_imports_search_roots_in_order(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    (a / "x").mkdir(parents=True)
    b.mkdir()
    (a / "x" / "page.jx").write_text('{# import "shared.jx" as S #}<S />')
    (b / "shared.jx").write_text("from b")
    result = run_minijx(a, b)
    assert result.returncode == 0, result.stderr
    from .helpers import load_module

    assert load_module(a / "x" / "page.py").render() == "from b"


@pytest.mark.skipif(not JX_VIEWS.exists(), reason="Jx docs views not available")
def test_jx_docs_views_compile(tmp_path):
    """The real templates that build the Jx documentation site."""
    dest = tmp_path / "views"
    dest.mkdir()
    sources = {p.name: p.read_text(encoding="utf-8") for p in JX_VIEWS.glob("*.jx")}
    # Templates using macros are out of minijx's scope by design, and so is
    # anything that imports them.
    skipped = {n for n, s in sources.items() if re.search(r"\{%-?\s*(macro|call|include|extends)\b", s)}
    while True:
        more = {
            n for n, s in sources.items()
            if n not in skipped and any(f'"./{x}"' in s or f'"{x}"' in s for x in skipped)
        }
        if not more:
            break
        skipped |= more
    for name, src in sources.items():
        if name in skipped:
            continue
        (dest / name).write_text(src, encoding="utf-8")
    assert len(sources) - len(skipped) >= 10, skipped
    result = run_minijx(dest)
    assert result.returncode == 0, result.stderr
    assert "0 failed" in result.stderr


def test_colliding_function_names_get_a_suffix(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "page.jx").write_text('{# import "a/b.jx" as AB #}{# import "a_b.jx" as A_B #}<AB /> <A_B />')
    (tmp_path / "a" / "b.jx").write_text("slash")
    (tmp_path / "a_b.jx").write_text("underscore")
    assert run_minijx(tmp_path).returncode == 0
    source = (tmp_path / "page.py").read_text()
    assert "def _c_a_b(" in source and "def _c_a_b_2(" in source
    from .helpers import load_module

    assert load_module(tmp_path / "page.py").render() == "slash underscore"


def test_relative_import_cannot_leave_its_folder(tmp_path):
    root = tmp_path / "components"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "page.jx").write_text('{# import "../../secret.jx" as S #}<S />')
    (tmp_path / "secret.jx").write_text("secret")
    result = run_minijx(root)
    assert result.returncode == 1
    assert "page.jx:1:1: Import `../../secret.jx` goes outside of the folder" in result.stderr


def test_unknown_option(tmp_path):
    result = run_minijx("--package", f"ui={tmp_path}")
    assert result.returncode == 2
    assert "unknown option --package" in result.stderr
