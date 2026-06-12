import pytest

from proper import channels, metadata


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the channels blueprint
    expects to already exist."""
    app_root = tmp_path / "myapp"

    for d in ("config", "assets/js"):
        (app_root / d).mkdir(parents=True)

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
    assert "CABLE:" in text

    # cable.js asset
    path = app_in_tmp.root_path / "assets" / "js" / "cable.js"
    assert path.exists()

    # turbo streams bridge lives in cable.js, imported from application.js
    js_dir = app_in_tmp.root_path / "assets" / "js"
    assert "turbo-stream-channel" in (js_dir / "cable.js").read_text()
    assert 'import "cable"' in (js_dir / "application.js").read_text()

    # config __init__ updated with channels import
    text = (app_in_tmp.root_path / "config" / "__init__.py").read_text()
    assert "from .channels import CABLE" in text

    # records the install in .proper
    assert metadata.is_installed(app_in_tmp, "channels")


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
