import logging
import os

import pytest
from minijx import CompileError

from proper import App
from proper.compile import compile_views, compiled_views_path, lower, views_are_compiled
from proper.helpers import logger


def _app(tmp_path, config=None):
    views = tmp_path / "myapp" / "views"
    if not views.exists():
        views.mkdir(parents=True)
        (views / "page.jx").write_text("{#def name #}<p>{{ name }}</p>")
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": False, **(config or {})})
    app.views_path = views
    app.catalog.add_folder(views)
    return app, views


def test_the_output_follows_config(tmp_path):
    app, _ = _app(tmp_path, {"COMPILED_PATH": "build/out"})
    assert app.catalog.output == (app.root_path.parent / "build" / "out").resolve()
    assert compiled_views_path(app) == app.catalog.output / "views"


def test_lower_compiles_the_views(tmp_path):
    app, _ = _app(tmp_path)
    lower(app)
    assert [p.name for p in compiled_views_path(app).glob("*.py")] == ["page.py"]
    assert app.catalog.render("page.jx", name="x") == "<p>x</p>"


def test_lower_reports_every_broken_view(tmp_path):
    app, views = _app(tmp_path)
    (views / "a.jx").write_text("{% if %}")
    (views / "b.jx").write_text("{{ 1 + }}")
    with pytest.raises(CompileError) as info:
        lower(app)
    assert "a.jx:1:" in str(info.value)
    assert "b.jx:1:" in str(info.value)


def test_without_a_compiler_the_compiled_views_are_used(tmp_path, caplog):
    app, _ = _app(tmp_path)
    compile_views(app)
    shipped, _ = _app(tmp_path)
    shipped.catalog.compiler = None
    with caplog.at_level(logging.INFO, logger=logger.name):
        assert compile_views(shipped) is False
    assert "No minijx compiler" in caplog.text
    assert shipped.catalog.render("page.jx", name="x") == "<p>x</p>"


def test_an_app_without_views(tmp_path):
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": False})
    assert app.catalog.folders == []
    assert compiled_views_path(app) == app.catalog.output / "views"
    lower(app)  # nothing to compile


def _make_newer(path, than):
    """Set the modification time of a file after the one of another."""
    mtime = than.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(mtime, mtime))


def test_views_are_compiled(tmp_path):
    app, views = _app(tmp_path)
    assert not views_are_compiled(app)

    compile_views(app)
    assert views_are_compiled(app)

    # A view that changed after it was compiled
    _make_newer(views / "page.jx", compiled_views_path(app) / "page.py")
    assert not views_are_compiled(app)


def test_views_are_compiled_checks_every_view(tmp_path):
    app, views = _app(tmp_path)
    (views / "sub").mkdir()
    (views / "sub" / "index.html.jx").write_text("<p>hi</p>")
    compile_views(app)
    assert views_are_compiled(app)

    (compiled_views_path(app) / "sub" / "index_html.py").unlink()
    assert not views_are_compiled(app)


def test_compiled_views_are_not_compiled_again(tmp_path, caplog):
    app, _ = _app(tmp_path)
    assert compile_views(app) is True
    module = compiled_views_path(app) / "page.py"
    mtime = module.stat().st_mtime_ns

    with caplog.at_level(logging.INFO, logger=logger.name):
        assert compile_views(app) is False

    assert "Using the compiled views" in caplog.text
    assert module.stat().st_mtime_ns == mtime
    assert app.catalog.render("page.jx", name="x") == "<p>x</p>"


def test_a_view_that_changed_is_compiled_again(tmp_path):
    app, views = _app(tmp_path)
    compile_views(app)
    (views / "page.jx").write_text("{#def name #}<b>{{ name }}</b>")
    _make_newer(views / "page.jx", compiled_views_path(app) / "page.py")

    assert compile_views(app) is True
    assert app.catalog.render("page.jx", name="x") == "<b>x</b>"


def test_force_compiles_the_compiled_views_again(tmp_path):
    app, _ = _app(tmp_path)
    compile_views(app)
    assert compile_views(app) is False
    assert compile_views(app, force=True) is True


def test_in_debug_mode_the_views_are_always_compiled(tmp_path):
    app, _ = _app(tmp_path, {"DEBUG": True})
    assert compile_views(app) is True
    assert compile_views(app) is True


def test_an_app_with_compiled_views_starts_without_writing(tmp_path):
    app, _ = _app(tmp_path)
    compile_views(app)
    folders = [app.catalog.output, *(p for p in app.catalog.output.rglob("*") if p.is_dir())]
    for folder in folders:
        folder.chmod(0o555)
    try:
        started, _ = _app(tmp_path)
        lower(started)
        assert started.catalog.render("page.jx", name="x") == "<p>x</p>"
    finally:
        for folder in folders:
            folder.chmod(0o755)
