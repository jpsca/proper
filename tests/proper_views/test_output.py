"""
The output folder for the compiled modules, and filters, tests and tags
added to a catalog after it is created.
"""

import os
import shutil
import subprocess

import pytest
from markupsafe import Markup

from proper.views import Catalog, ComponentNotCompiledError
from proper.views.catalog import output_names
from .helpers import BIN


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


def py_files(folder):
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*.py"))


# Output folder


def test_modules_go_to_the_output_folder(tmp_path):
    views, out = tmp_path / "app" / "views", tmp_path / "build"
    write(views, {
        "pages/home.html.jx": '{# import "card.jx" as Card #}{# def v #}<Card v={{ v }} />',
        "card.jx": "{# def v #}<b>{{ v }}</b>",
    })
    catalog = Catalog(views, output=out)
    catalog.compile()
    assert py_files(views) == []
    assert py_files(out) == ["views/card.py", "views/pages/home_html.py"]
    assert catalog.render("pages/home.html.jx", v="<v>") == "<b>&lt;v&gt;</b>"


def test_compiled_on_render(tmp_path):
    views, out = tmp_path / "views", tmp_path / "build"
    write(views, {"card.jx": "a"})
    catalog = Catalog(views, output=out)
    assert catalog.render("card.jx") == "a"
    assert py_files(out) == ["views/card.py"]
    write(views, {"card.jx": "b"})
    t = os.stat(out / "views" / "card.py").st_mtime + 5
    os.utime(views / "card.jx", (t, t))
    assert catalog.render("card.jx") == "b"


def test_folders_with_the_same_name(tmp_path):
    a, b, out = tmp_path / "a" / "views", tmp_path / "b" / "views", tmp_path / "build"
    write(a, {"page.jx": "from a"})
    write(b, {"page.jx": "from b", "only_b.jx": "only b"})
    catalog = Catalog(a, output=out)
    catalog.add_folder(b)
    catalog.compile()
    assert py_files(out) == ["views-2/only_b.py", "views-2/page.py", "views/page.py"]
    assert catalog.render("page.jx") == "from a"
    assert catalog.render("only_b.jx") == "only b"


def test_output_names():
    from pathlib import Path

    assert output_names([Path("/x/views"), Path("/y/views"), Path("/z/ui"), Path("/w/views")]) == [
        "views", "views-2", "ui", "views-3",
    ]


def test_deployed_without_the_sources(tmp_path):
    """Built ahead, shipped without the `.jx` files, rendered without a compiler."""
    views, out = tmp_path / "views", tmp_path / "build"
    write(views, {"card.jx": "{# def v #}<b>{{ v }}</b>"})
    Catalog(views, output=out).compile()
    shutil.rmtree(views)
    views.mkdir()
    catalog = Catalog(views, output=out, compiler=False, auto_reload=False)
    assert catalog.render("card.jx", v="x") == "<b>x</b>"


def test_the_project_can_move(tmp_path):
    """The sources a module records are relative to it."""
    project = tmp_path / "project"
    write(project / "views", {"page.jx": '{# import "card.jx" as Card #}<Card />', "card.jx": "c"})
    Catalog(project / "views", output=project / "build").compile()
    moved = tmp_path / "moved"
    shutil.copytree(project, moved)
    shutil.rmtree(project)
    catalog = Catalog(moved / "views", output=moved / "build", compiler=False)
    assert catalog.render("page.jx") == "c"


def test_compiler_args_with_output(tmp_path):
    catalog = Catalog(tmp_path, output=tmp_path / "out")
    assert catalog.compiler_args()[3] == f"--output={(tmp_path / 'out').resolve()}"


def test_cli_output_needs_a_folder(tmp_path):
    result = subprocess.run([str(BIN), "--output=", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--output needs a folder" in result.stderr


# Added after the catalog is created


def test_add_filters_and_globals(tmp_path):
    write(tmp_path, {"card.jx": "{# def v #}{{ v | shout }} {{ site }}"})
    catalog = Catalog(tmp_path)
    catalog.add_filters({"shout": lambda s: s.upper() + "!"})
    catalog.globals["site"] = "Demo"
    assert catalog.render("card.jx", v="hi") == "HI! Demo"
    # already loaded: the next render sees the change
    catalog.add_filters({"shout": lambda s: s.upper() + "?"})
    assert catalog.render("card.jx", v="hi") == "HI? Demo"


def test_add_filters_keeps_the_previous_ones(tmp_path):
    write(tmp_path, {"card.jx": "{{ 'a' | one }}{{ 'b' | two }}{{ 'c' is short }}"})
    catalog = Catalog(tmp_path, filters={"one": str.upper})
    catalog.add_filters({"two": lambda s: s * 2})
    catalog.add_tests({"short": lambda s: len(s) < 2})
    assert catalog.render("card.jx") == "AbbTrue"


def test_add_filters_cannot_replace_trusted_ones(tmp_path):
    catalog = Catalog(tmp_path)
    with pytest.raises(ValueError, match="Cannot replace the filter"):
        catalog.add_filters({"safe": str})
    Catalog(tmp_path, autoescape=False).add_filters({"safe": str})


def test_add_tags_recompiles(tmp_path):
    write(tmp_path, {"card.jx": "{% box %}x{% endbox %}"})
    catalog = Catalog(tmp_path)
    catalog.add_tags({"box": lambda *, caller, template: Markup(f"[{caller()}]")})
    assert catalog.tags == ("box",)
    assert catalog.render("card.jx") == "[x]"
    # a new name: modules compiled before are stale
    catalog.add_tags({"other": lambda *, caller, template: ""})
    assert catalog.tags == ("box", "other")
    assert catalog.render("card.jx") == "[x]"
    assert "'other'" in (tmp_path / "card.py").read_text()


def test_add_tags_without_compiler(tmp_path):
    write(tmp_path, {"card.jx": "x"})
    Catalog(tmp_path).compile()
    catalog = Catalog(tmp_path, compiler=False)
    assert catalog.render("card.jx") == "x"
    catalog.add_tags({"box": lambda *, caller, template: ""})
    with pytest.raises(ComponentNotCompiledError):
        catalog.render("card.jx")


def test_concurrent_compiles(tmp_path):
    """The workers of a server compile the same folder at the same time:
    every module is whole, and no temporary file is left."""
    import threading

    views, out = tmp_path / "views", tmp_path / "build"
    write(views, {f"c{i}.jx": f"{{# def v #}}<p>{i} {{{{ v }}}}</p>" * 50 for i in range(20)})
    errors = []

    def compile_it():
        try:
            Catalog(views, output=out).compile()
        except Exception as err:  # pragma: no cover
            errors.append(err)

    threads = [threading.Thread(target=compile_it) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert errors == []
    assert not list(out.rglob("*.tmp"))
    catalog = Catalog(views, output=out, compiler=False)
    assert all(catalog.render(f"c{i}.jx", v="x").startswith(f"<p>{i} x</p>") for i in range(20))


def test_a_module_compiled_from_another_file_is_stale(tmp_path):
    """Two catalogs whose folders have the same name, sharing an output
    folder: each recompiles the module of the other."""
    a, b, out = tmp_path / "a" / "views", tmp_path / "b" / "views", tmp_path / "build"
    write(a, {"page.jx": "from a"})
    write(b, {"page.jx": "from b"})
    assert Catalog(a, output=out).render("page.jx") == "from a"
    assert Catalog(b, output=out).render("page.jx") == "from b"
    assert Catalog(a, output=out).render("page.jx") == "from a"
    with pytest.raises(ComponentNotCompiledError, match="was compiled from another file"):
        Catalog(b, output=out, compiler=False, auto_reload=False).render("page.jx")


def test_symlinked_folder(tmp_path):
    real = tmp_path / "real"
    write(real, {"page.jx": "x"})
    (tmp_path / "link").symlink_to(real)
    catalog = Catalog(tmp_path / "link", output=tmp_path / "build")
    assert catalog.render("page.jx") == "x"
    mtime = (tmp_path / "build" / "real" / "page.py").stat().st_mtime_ns
    assert Catalog(tmp_path / "link", output=tmp_path / "build").render("page.jx") == "x"
    assert (tmp_path / "build" / "real" / "page.py").stat().st_mtime_ns == mtime


# render_string


def test_render_string(tmp_path):
    write(tmp_path, {"ui/card.jx": "{# def title #}<b>{{ title }}</b>"})
    catalog = Catalog(tmp_path)
    source = '{# import "ui/card.jx" as Card #}{# def v #}<Card title={{ v }} />'
    assert catalog.render_string(source, v="<x>") == "<b>&lt;x&gt;</b>"
    assert isinstance(catalog.render_string(source, v="y"), Markup)
    # compiled once
    assert len(catalog._strings) == 1
    # without autoescape, and with globals
    plain = Catalog(tmp_path, autoescape=False, site="S")
    assert plain.render_string("{# def v #}{{ site }} {{ v }}", v="<x>") == "S <x>"
    assert py_files(tmp_path) == []  # nothing was compiled into the folders


def test_render_string_follows_its_imports(tmp_path):
    write(tmp_path, {"card.jx": "a"})
    catalog = Catalog(tmp_path)
    source = '{# import "card.jx" as Card #}<Card />'
    assert catalog.render_string(source) == "a"
    write(tmp_path, {"card.jx": "b"})
    t = os.stat(tmp_path / "card.jx").st_mtime + 5
    os.utime(tmp_path / "card.jx", (t, t))
    assert catalog.render_string(source) == "b"


def test_render_string_errors(tmp_path):
    from proper.views import CompileError

    catalog = Catalog(tmp_path)
    with pytest.raises(CompileError, match=r"^<string>:1:8: Unexpected end of expression"):
        catalog.render_string("{{ 1 + }}")
    with pytest.raises(ComponentNotCompiledError, match="needs the minijx compiler"):
        Catalog(tmp_path, compiler=False).render_string("x")


def test_render_string_with_tags_and_filters(tmp_path):
    catalog = Catalog(
        tmp_path,
        filters={"shout": lambda s: s.upper()},
        tags={"box": lambda *, caller, template: Markup(f"[{caller()}]")},
    )
    assert catalog.render_string("{% box %}{{ 'a' | shout }}{% endbox %}") == "[A]"


def test_cli_only(tmp_path):
    write(tmp_path, {"a.jx": "a", "b.jx": '{# import "c.jx" as C #}<C />', "c.jx": "c"})
    result = subprocess.run([str(BIN), f"--only={tmp_path / 'b.jx'}", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert py_files(tmp_path) == ["b.py"]
