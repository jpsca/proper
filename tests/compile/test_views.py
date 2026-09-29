import logging

import pytest
from minijx import CompileError

from proper import App
from proper.compile import compile_views, compiled_views_path, lower
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
