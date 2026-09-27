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
    assert "check" in app.CLI.jx()._commands


def test_check_ok(cli, capsys):
    cli.check()
    out = capsys.readouterr().out
    assert "card.jx - OK" in out
    assert "page.jx - OK" in out
    assert "2 components checked, 0 errors" in out


def test_check_json(cli, capsys):
    cli.check(format="json")
    data = json.loads(capsys.readouterr().out)
    assert data == {"checked": 2, "errors": []}


def test_check_exits_on_errors(app, capsys):
    app, views = app
    (views / "bad.jx").write_text('{#import "nope.jx" as Nope #}<Nope />')
    app.catalog.add_folder(views)
    cli = get_jx_cli(app)()
    with pytest.raises(SystemExit) as exc:
        cli.check()
    assert exc.value.code == 1
    assert "bad.jx" in capsys.readouterr().out


def test_info(cli, app, capsys):
    _, views = app
    cli.info()
    out = capsys.readouterr().out
    assert "components: 2" in out
    assert str(views) in out


def test_info_json(cli, capsys):
    cli.info(format="json")
    data = json.loads(capsys.readouterr().out)
    assert data["components"] == ["card.jx", "page.jx"]


def test_parse_file(cli, app, capsys):
    _, views = app
    cli.parse(str(views / "page.jx"))
    data = json.loads(capsys.readouterr().out)
    assert [imp["name"] for imp in data["imports"]] == ["Card"]
    assert [tag["name"] for tag in data["tags"]] == ["Card"]
    assert data["errors"] == []


def test_parse_text_from_stdin(cli, monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO('{#import "card.jx" as Card #}<Card />'))
    cli.parse("buffer.jx", stdin=True, format="text")
    out = capsys.readouterr().out
    assert "import card.jx as Card" in out
    assert "<Card>" in out


def test_parse_exits_on_errors(cli, app):
    _, views = app
    (views / "broken.jx").write_text('{#import "card.jx" as Card #}\n<div>\n  <Card>\n</div>\n')
    with pytest.raises(SystemExit) as exc:
        cli.parse(str(views / "broken.jx"))
    assert exc.value.code == 1


def test_collect_assets(app, tmp_path, capsys):
    app, _ = app
    pkg = tmp_path / "pkg"
    (pkg / "assets").mkdir(parents=True)
    (pkg / "assets" / "ui.css").write_text("a{}")
    (pkg / "button.jx").write_text("<button />")
    app.catalog.add_folder(pkg, prefix="ui", assets=pkg / "assets")
    output = tmp_path / "out"

    get_jx_cli(app)().collect_assets(str(output))

    out = capsys.readouterr().out
    assert "ui/ui.css" in out
    assert "1 file collected" in out
    assert (output / "ui" / "ui.css").read_text() == "a{}"


def test_collect_assets_none(cli, tmp_path, capsys):
    cli.collect_assets(str(tmp_path / "out"))
    assert "0 files collected" in capsys.readouterr().out
