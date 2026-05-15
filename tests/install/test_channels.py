"""Tests for proper.install.channels — installs channels blueprint into an app."""

import pytest

from proper.install import channels


APP_NAME = "myapp"

CONFIG_INIT = """\
from .main import *  # noqa
"""


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the channels blueprint
    expects to already exist."""
    app_root = tmp_path / APP_NAME

    for d in ("config", "assets/js"):
        (app_root / d).mkdir(parents=True)

    (app_root / "config" / "__init__.py").write_text(CONFIG_INIT)

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_file_creation(app_in_tmp):
    channels.install(app_in_tmp)

    # channels config file
    path = app_in_tmp.root_path / "config" / "channels.py"
    assert path.exists()
    text = path.read_text()
    assert "CABLE_PATH" in text
    assert "CHANNELS" in text
    assert APP_NAME in text

    # cable.js asset
    path = app_in_tmp.root_path / "assets" / "js" / "cable.js"
    assert path.exists()

    # config __init__ updated with channels import
    text = (app_in_tmp.root_path / "config" / "__init__.py").read_text()
    assert "from .channels import CHANNELS" in text
