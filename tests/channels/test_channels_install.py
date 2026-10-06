import pytest

from proper import channels, metadata


@pytest.fixture(autouse=True)
def commands(monkeypatch):
    """What the installer would run (`uv add ...`), instead of running it."""
    ran = []
    monkeypatch.setattr("proper.helpers.render.call", ran.append)
    return ran


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the channels blueprint
    expects to already exist."""
    app_root = tmp_path / "myapp"

    (app_root / "config").mkdir(parents=True)
    (tmp_path / "assets" / "js").mkdir(parents=True)

    CONFIG_INIT = "\nfrom .main import *  # noqa\n"
    (app_root / "config" / "__init__.py").write_text(CONFIG_INIT)

    app.root_path = app_root
    app.name = "myapp"
    return app


def test_file_creation(app_in_tmp):
    channels.install(app_in_tmp)

    # channels config file
    path = app_in_tmp.root_path / "config" / "channels.py"
    assert path.exists()
    text = path.read_text()
    assert "CABLE_PATH" in text
    assert "CABLE_PORT" in text
    assert "CABLE:" in text
    # WseCable, with no Redis to run; the other backends are left as comments
    assert 'CABLE: dict = {"type": "proper.channels.wse.WseCable"}' in text
    assert "#     CABLE = {}" in text
    assert '#         "type": "proper.channels.RedisCable",' in text
    assert '"prefix": "myapp:cable:"' in text

    # cable.js asset
    path = app_in_tmp.root_path.parent / "assets" / "js" / "cable.js"
    assert path.exists()

    # turbo streams bridge lives in cable.js, imported from application.js
    js_dir = app_in_tmp.root_path.parent / "assets" / "js"
    assert "turbo-stream-channel" in (js_dir / "cable.js").read_text()
    assert 'meta[name="cable-port"]' in (js_dir / "cable.js").read_text()
    assert 'import "cable"' in (js_dir / "application.js").read_text()

    # config __init__ updated with channels import
    text = (app_in_tmp.root_path / "config" / "__init__.py").read_text()
    assert "from .channels import CABLE" in text
    assert "CABLE_PORT" in text

    # records the install in .proper
    assert metadata.is_installed(app_in_tmp, "channels")


def test_proper_wse_is_added_as_a_dependency(app_in_tmp, commands):
    (app_in_tmp.root_path.parent / "uv.lock").write_text("")
    channels.install(app_in_tmp)
    assert commands == ['uv add "proper-wse >= 2.6.0"']


def test_the_generated_config_serves_with_wse_cable(app_in_tmp, monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("CABLE_PORT", raising=False)
    channels.install(app_in_tmp)
    namespace = {}
    exec((app_in_tmp.root_path / "config" / "channels.py").read_text(), namespace)
    assert namespace["CABLE"] == {"type": "proper.channels.wse.WseCable"}
    assert namespace["CABLE_PORT"] == 2301


def test_app_channel_created(app_in_tmp):
    channels.install(app_in_tmp)

    path = app_in_tmp.root_path / "channels" / "app_channel.py"
    assert path.exists()
    text = path.read_text()
    assert "class AppChannel(Channel):" in text
    assert "Session = Session" in text
    # picks up the auth Session model when present, anonymous otherwise
    assert "from ..models import Session" in text
    assert "except ImportError:" in text
