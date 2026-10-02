import json
import os

import pytest

from proper import App
from proper.cli.jx_cli import get_jx_cli
from proper.compile import compiled_views_path, views_are_compiled


@pytest.fixture()
def app(tmp_path):
    views = tmp_path / "views"
    views.mkdir()
    (views / "card.jx").write_text("{#def title #}<div>{{ title }}</div>")
    (views / "page.jx").write_text('{#import "card.jx" as Card #}<Card title="x" />')
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": False})
    app.catalog.add_folder(views)
    return app, views


@pytest.fixture()
def cli(app):
    app, _ = app
    return get_jx_cli(app)()


def test_registered_in_the_app_cli(app):
    app, _ = app
    assert "info" in app.CLI.jx()._commands
    assert "compile" in app.CLI.jx()._commands


def test_compile(cli, app, capsys):
    app, _ = app
    cli.compile()
    out = capsys.readouterr().out
    assert out == f"Compiled 2 views into {app.catalog.output}\n"
    assert views_are_compiled(app)
    assert app.catalog.render("page.jx") == "<div>x</div>"


def test_compile_again(cli, app, capsys):
    """Unlike the start of the app, the command always compiles."""
    app, _ = app
    cli.compile()
    module = compiled_views_path(app) / "page.py"
    module.write_text("stale")
    os.utime(module, ns=(2**62, 2**62))  # newer than its view

    cli.compile()

    assert "stale" not in module.read_text()
    assert "Compiled 2 views" in capsys.readouterr().out


def test_compile_reports_every_broken_view(cli, app, capsys):
    app, views = app
    (views / "a.jx").write_text("{% if %}")
    (views / "b.jx").write_text("{{ 1 + }}")

    with pytest.raises(SystemExit) as info:
        cli.compile()

    assert info.value.code == 1
    captured = capsys.readouterr()
    assert "a.jx:1:" in captured.err
    assert "b.jx:1:" in captured.err
    assert captured.out == ""


def test_compile_without_a_compiler(cli, app, capsys):
    app, _ = app
    app.catalog.compiler = None

    with pytest.raises(SystemExit) as info:
        cli.compile()

    assert info.value.code == 1
    assert "no minijx compiler" in capsys.readouterr().err


def test_info(cli, app, capsys):
    app, views = app
    cli.info()
    out = capsys.readouterr().out
    assert f"Folders:    {views.resolve()}" in out
    assert "Autoescape: html, jx, xml" in out
    assert "Tags:       cache, frame, stream" in out
    assert "Views:      2" in out
    assert "  page.jx" in out


def test_info_json(cli, app, capsys):
    app, views = app
    cli.info(format="json")
    data = json.loads(capsys.readouterr().out)
    assert data["folders"] == [str(views.resolve())]
    assert data["output"] == str(app.catalog.output)
    assert data["tags"] == ["cache", "frame", "stream"]
    assert data["views"] == ["card.jx", "page.jx"]
