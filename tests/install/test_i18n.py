"""Tests for proper.install.i18n — installs i18n blueprint into an app."""

import pytest

from proper.install import i18n, metadata


APP_CONTROLLER = """\
from proper.controller import Controller


class AppController(
    Controller,
    Authentication,
):
    pass
"""


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the i18n blueprint
    expects to already exist."""
    app_root = tmp_path / "myapp"

    for d in ("controllers", "config"):
        (app_root / d).mkdir(parents=True)

    (app_root / "controllers" / "app_controller.py").write_text(APP_CONTROLLER)

    app.root_path = app_root
    app.name = "myapp"
    return app


def test_file_creation(app_in_tmp):
    i18n.install(app_in_tmp)

    # locale_config_dir
    path = app_in_tmp.root_path / "config" / "locales"
    assert path.is_dir()

    # en_locale
    path = app_in_tmp.root_path / "config" / "locales" / "en.yml"
    assert path.exists()

    # locale_readme
    path = app_in_tmp.root_path / "config" / "locales" / "README.md"
    assert path.exists()

    text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
    assert "CurrentLocale" in text
    assert "CurrentTimezone" in text

    # adds_current_locale_concern
    text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
    assert "CurrentLocale," in text

    # adds_current_timezone_concern
    text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
    assert "CurrentTimezone," in text

    # aimezone_concern_inserted_after_authentication
    text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
    # The class body should have CurrentTimezone after Authentication
    class_start = text.index("class AppController")
    class_body = text[class_start:]
    auth_pos = class_body.index("Authentication,")
    tz_pos = class_body.index("CurrentTimezone,")
    assert tz_pos > auth_pos

    # records the install in .properfrom proper.install import metadata
    assert metadata.is_installed(app_in_tmp, "i18n")
