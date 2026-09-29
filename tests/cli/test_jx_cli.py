import json

import pytest

from proper import App
from proper.cli.jx_cli import get_jx_cli


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


def test_info(cli, app, capsys):
    app, views = app
    cli.info()
    out = capsys.readouterr().out
    assert f"Folders:    {views.resolve()}" in out
    assert "Autoescape: html, jx, xml" in out
    assert "Tags:       cache, turbo_frame, turbo_stream" in out
    assert "Views:      2" in out
    assert "  page.jx" in out


def test_info_json(cli, app, capsys):
    app, views = app
    cli.info(format="json")
    data = json.loads(capsys.readouterr().out)
    assert data["folders"] == [str(views.resolve())]
    assert data["output"] == str(app.catalog.output)
    assert data["tags"] == ["cache", "turbo_frame", "turbo_stream"]
    assert data["views"] == ["card.jx", "page.jx"]
