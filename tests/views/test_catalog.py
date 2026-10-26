"""
The output file naming and the runtime Catalog.
"""

import os
import time

import pytest

from proper.views import (
    Catalog,
    CompileError,
    ComponentNotCompiledError,
    ComponentNotFoundError,
)
from proper.views.catalog import module_path
from .helpers import BIN, collapse, run_jxc


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


def touch_later(path, seconds=5):
    """Move a file's mtime forward, so the test does not depend on clock resolution."""
    t = time.time() + seconds
    os.utime(path, (t, t))


# Output naming


def test_dots_in_the_name_become_underscores(tmp_path):
    write(tmp_path, {"sitemap.xml.jx": "<urlset/>", "sub/robots.txt.jx": "User-agent: *", "plain.jx": "x"})
    result = run_jxc(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "sitemap_xml.py").is_file()
    assert (tmp_path / "sub" / "robots_txt.py").is_file()
    assert (tmp_path / "plain.py").is_file()
    assert not (tmp_path / "sitemap.xml.py").exists()


def test_two_sources_for_one_output_is_an_error(tmp_path):
    write(tmp_path, {"a.b.jx": "one", "a_b.jx": "two"})
    result = run_jxc(tmp_path)
    assert result.returncode == 1
    assert "a_b.py would overwrite the one compiled from" in result.stderr


def test_module_path_matches_the_compiler(tmp_path):
    assert module_path(tmp_path / "x" / "sitemap.xml.jx") == tmp_path / "x" / "sitemap_xml.py"
    assert module_path(tmp_path / "card.jx") == tmp_path / "card.py"


# Catalog


@pytest.fixture
def components(tmp_path):
    folder = tmp_path / "components"
    write(folder, {
        "layout.jx": """{# css "layout.css" #}{# js "layout.js" #}{# def title #}
<html><head><title>{{ title }} · {{ site_name }}</title>{{ assets.render() }}</head>
<body {{ attrs.render(class="page") }}>{{ content }}</body></html>
""",
        "pages/home.jx": """{# import "layout.jx" as Layout #}{# import "./card.jx" as Card #}
{# css "home.css" #}{# def items=[] #}
<Layout title="Home"><Card title={{ user }} />{% for i in items %}<i>{{ i }}</i>{% endfor %}</Layout>
""",
        "pages/card.jx": '{# css "card.css" #}{# def title #}<div class="card">{{ title | upper }}</div>',
        "sitemap.xml.jx": "{# def urls #}<urlset>{% for u in urls %}<url>{{ u }}</url>{% endfor %}</urlset>",
    })
    result = run_jxc(folder)
    assert result.returncode == 0, result.stderr
    return folder


def test_render_by_name(components):
    catalog = Catalog(components, site_name="Demo")
    html = catalog.render("pages/home.jx", globals={"user": "ana"}, items=[1, 2], id="main")
    assert "<title>Home · Demo</title>" in html
    assert '<div class="card">ANA</div>' in html
    assert "<i>1</i><i>2</i>" in html


def test_render_name_without_extension_and_double_extension(components):
    catalog = Catalog(components)
    assert catalog.render("sitemap.xml", urls=["/a"]) == "<urlset><url>/a</url></urlset>"
    assert catalog.render("sitemap.xml.jx", urls=[]) == "<urlset></urlset>"
    assert catalog.render("/pages\\card.jx", title="x") == '<div class="card">X</div>'


def test_extra_kwargs_become_attrs(components):
    catalog = Catalog(components, site_name="S")
    html = catalog.render("layout.jx", title="T", id="b", **{"class": "dark"}, data_x=1)
    assert '<body class="page dark" data-x="1" id="b">' in html


def test_assets_global_lists_the_whole_tree(components):
    catalog = Catalog(components, site_name="S")
    html = catalog.render("pages/home.jx", globals={"user": "u"})
    # Assets belong to the component the catalog rendered, in Jx's order:
    # its own first, then each import's.
    assert (
        '<link rel="stylesheet" href="home.css">\n'
        '<link rel="stylesheet" href="layout.css">\n'
        '<link rel="stylesheet" href="card.css">\n'
        '<script type="module" src="layout.js"></script>'
    ) in html
    co = catalog.get_component("pages/home.jx")
    assert co.collect_css() == ["home.css", "layout.css", "card.css"]
    assert co.render_js(module=False, defer=True) == '<script src="layout.js" defer></script>'


def test_render_globals_override_catalog_globals(components):
    catalog = Catalog(components, site_name="Catalog")
    html = catalog.render("layout.jx", globals={"site_name": "Render"}, title="t")
    assert "t · Render" in html


def test_random_id_global(tmp_path):
    write(tmp_path, {"a.jx": '{{ _get_random_id("btn") }}'})
    run_jxc(tmp_path)
    html = Catalog(tmp_path).render("a.jx")
    assert html.startswith("btn-") and len(html) == 36


def test_not_found(components):
    catalog = Catalog(components)
    with pytest.raises(ComponentNotFoundError):
        catalog.render("nope.jx")
    assert not catalog.has_component("nope")
    assert catalog.has_component("pages/home")


def test_first_folder_wins(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    write(a, {"x.jx": "from a"})
    write(b, {"x.jx": "from b", "y.jx": "only b"})
    assert run_jxc(a, b).returncode == 0
    catalog = Catalog(a)
    catalog.add_folder(b)
    assert catalog.render("x.jx") == "from a"
    assert catalog.render("y.jx") == "only b"


def test_missing_module_without_compiler(tmp_path):
    write(tmp_path, {"a.jx": "hi"})
    with pytest.raises(ComponentNotCompiledError, match=r"call `catalog\.compile\(\)`"):
        Catalog(tmp_path, compiler=False).render("a.jx")


def test_recompiles_when_a_dependency_changes(tmp_path):
    write(tmp_path, {"a.jx": "old", "b.jx": '{# import "a.jx" as A #}[<A />]'})
    catalog = Catalog(tmp_path, compiler=BIN)
    assert catalog.render("b.jx") == "[old]"
    (tmp_path / "a.jx").write_text("new")
    touch_later(tmp_path / "a.jx")
    # b.py has its own copy of a; only its SOURCES tell it is stale.
    assert catalog.render("b.jx") == "[new]"


def test_stale_module_without_compiler_is_an_error(tmp_path):
    write(tmp_path, {"a.jx": "old"})
    run_jxc(tmp_path)
    catalog = Catalog(tmp_path, compiler=False)
    assert catalog.render("a.jx") == "old"
    touch_later(tmp_path / "a.jx")
    with pytest.raises(ComponentNotCompiledError):
        catalog.render("a.jx")


def test_reloads_a_recompiled_module(tmp_path):
    write(tmp_path, {"a.jx": "one"})
    run_jxc(tmp_path)
    catalog = Catalog(tmp_path)
    assert catalog.render("a.jx") == "one"
    (tmp_path / "a.jx").write_text("two")
    touch_later(tmp_path / "a.jx", 5)
    run_jxc(tmp_path)
    touch_later(tmp_path / "a.py", 10)
    assert catalog.render("a.jx") == "two"


def test_auto_reload_off_keeps_the_loaded_module(tmp_path):
    write(tmp_path, {"a.jx": "one"})
    run_jxc(tmp_path)
    catalog = Catalog(tmp_path, auto_reload=False, compiler=BIN)
    assert catalog.render("a.jx") == "one"
    (tmp_path / "a.jx").write_text("two")
    touch_later(tmp_path / "a.jx")
    assert catalog.render("a.jx") == "one"


def test_same_html_as_jx_catalog(project):
    """Render through both catalogs, assets included."""
    project.write({
        "layout.jx": '{# css "l.css" #}{# js "l.js" #}{# def title #}<head>{{ assets.render() }}</head><h1>{{ title }}</h1>{{ content }}',
        "page.jx": '{# import "layout.jx" as Layout #}{# css "p.css" #}{# def n #}<Layout title="T">{% for i in range(n) %}<b>{{ i }}</b>{% endfor %}</Layout>',
    })
    assert project.compile().returncode == 0

    mini = Catalog(project.mini).render("page.jx", n=3)
    jx = project.render_jx("page.jx", n=3)
    assert collapse(mini) == collapse(jx)


def test_a_broken_file_does_not_break_the_others(tmp_path):
    write(tmp_path, {"good.jx": "fine", "bad.jx": "{{ 1 + }}"})
    catalog = Catalog(tmp_path, compiler=BIN)
    assert catalog.render("good.jx") == "fine"
    with pytest.raises(CompileError, match=r"bad\.jx:1:8"):
        catalog.render("bad.jx")


def test_broken_dependency_is_reported_for_the_importer(tmp_path):
    write(tmp_path, {"page.jx": '{# import "dep.jx" as Dep #}<Dep />', "dep.jx": "{% if %}"})
    with pytest.raises(CompileError, match=r"dep\.jx:1:1"):
        Catalog(tmp_path, compiler=BIN).render("page.jx")


# catalog.compile()


def test_compile_builds_everything(tmp_path):
    write(tmp_path, {"page.jx": '{# import "other/x.jx" as X #}[<X />]', "other/x.jx": "x"})
    catalog = Catalog(tmp_path, compiler=BIN, auto_reload=False)
    catalog.compile()
    assert (tmp_path / "page.py").is_file() and (tmp_path / "other" / "x.py").is_file()
    assert catalog.render("page.jx") == "[x]"


def test_compile_reports_every_error(tmp_path):
    write(tmp_path, {"a.jx": "{{ 1 + }}", "b.jx": "{% if x %}", "ok.jx": "ok"})
    catalog = Catalog(tmp_path, compiler=BIN)
    with pytest.raises(CompileError) as err:
        catalog.compile()
    assert "a.jx:1:8" in str(err.value) and "b.jx:1:1" in str(err.value)
    assert (tmp_path / "ok.py").is_file()


def test_default_compiler_is_the_bundled_one(tmp_path):
    from proper.views.catalog import bundled_compiler

    assert bundled_compiler() is not None, "run `make build`: it copies the binary into the package"
    catalog = Catalog(tmp_path)
    assert catalog.compiler == str(bundled_compiler())
    write(tmp_path, {"a.jx": "a"})
    catalog.compile()
    assert (tmp_path / "a.py").is_file()


def test_a_compiler_in_the_path_is_not_used(tmp_path, monkeypatch):
    """Only the one built with Proper: another could be of another version."""
    import proper.views.catalog

    monkeypatch.setattr(proper.views.catalog, "bundled_compiler", lambda: None)
    monkeypatch.setenv("PATH", f"{BIN.parent}{os.pathsep}{os.environ.get('PATH', '')}")
    write(tmp_path, {"a.jx": "a"})
    assert Catalog(tmp_path).compiler is None


def test_compile_without_a_binary(tmp_path, monkeypatch):
    import proper.views.catalog

    monkeypatch.setattr(proper.views.catalog, "bundled_compiler", lambda: None)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with pytest.raises(FileNotFoundError, match="No views compiler"):
        Catalog(tmp_path).compile()
    with pytest.raises(FileNotFoundError, match="compiler=False"):
        Catalog(tmp_path, compiler=False).compile()


def fake_compiler(tmp_path, version_line: str):
    script = tmp_path / "fake-jxc"
    script.write_text(f"#!/bin/sh\necho '{version_line}'\n")
    script.chmod(0o755)
    return script


def test_compiler_with_another_module_format_is_refused(tmp_path):
    from proper.views.catalog import MODULE_FORMAT

    fake = fake_compiler(tmp_path, f"jxc 9.9.9 (module format {MODULE_FORMAT + 1})")
    write(tmp_path, {"a.jx": "a"})
    with pytest.raises(CompileError, match=f"generates modules of format {MODULE_FORMAT + 1}"):
        Catalog(tmp_path, compiler=fake).compile()
    with pytest.raises(CompileError, match="generates modules of format"):
        Catalog(tmp_path, compiler=fake).render("a.jx")


def test_something_else_named_jxc_is_refused(tmp_path):
    fake = fake_compiler(tmp_path, "hello")
    with pytest.raises(CompileError, match="does not look like the views compiler"):
        Catalog(tmp_path, compiler=fake).compile()


def test_compiler_args_are_the_folders_in_order(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    catalog = Catalog(b)
    catalog.add_folder(a)
    assert catalog.compiler_args() == [
        "--autoescape=html,jx,xml", "--tags=", "--pure=", str(b.resolve()), str(a.resolve()),
    ]


def test_module_from_another_version_is_stale(tmp_path):
    write(tmp_path, {"a.jx": "new"})
    # format 2 stored assets as (prefix, url) pairs
    (tmp_path / "a.py").write_text(
        "VIEWS_FORMAT = 2\nCSS = (('', 'x.css'),)\nJS = ()\nSOURCES = ('a.jx',)\n"
        "render = lambda **kw: 'old'\n"
    )
    os.utime(tmp_path / "a.py", (2e9, 2e9))  # newer than a.jx
    with pytest.raises(ComponentNotCompiledError, match="another version"):
        Catalog(tmp_path, compiler=False, auto_reload=False).render("a.jx")
    # checked when first loaded, in any mode: compiled again
    assert Catalog(tmp_path, compiler=BIN, auto_reload=False).render("a.jx") == "new"
