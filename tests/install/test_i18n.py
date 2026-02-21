"""Tests for proper.install.i18n — installs i18n blueprint into an app."""

import pytest

from proper.install.i18n import SORT_IMPORTS_IN, install


APP_NAME = "myapp"

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
    app_root = tmp_path / APP_NAME

    for d in ("controllers", "config"):
        (app_root / d).mkdir(parents=True)

    (app_root / "controllers" / "app_controller.py").write_text(APP_CONTROLLER)

    app.root_path = app_root
    app.name = APP_NAME
    return app


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


class TestFileCreation:
    def test_creates_locale_config_dir(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "config" / "locales"
        assert path.is_dir()

    def test_creates_en_locale(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "config" / "locales" / "en.yml"
        assert path.exists()

    def test_creates_locale_readme(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "config" / "locales" / "README.md"
        assert path.exists()


# ---------------------------------------------------------------------------
# Prepended content
# ---------------------------------------------------------------------------


class TestPrependedContent:
    def test_prepends_imports_to_app_controller(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        assert "CurrentLocale" in text
        assert "CurrentTimezone" in text


# ---------------------------------------------------------------------------
# add_to_concerns
# ---------------------------------------------------------------------------


class TestConcerns:
    def test_adds_current_locale_concern(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        assert "CurrentLocale," in text

    def test_adds_current_timezone_concern(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        assert "CurrentTimezone," in text

    def test_timezone_concern_inserted_after_authentication(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        # The class body should have CurrentTimezone after Authentication
        class_start = text.index("class AppController")
        class_body = text[class_start:]
        auth_pos = class_body.index("Authentication,")
        tz_pos = class_body.index("CurrentTimezone,")
        assert tz_pos > auth_pos


# ---------------------------------------------------------------------------
# sort_imports_in
# ---------------------------------------------------------------------------


class TestSortImports:
    def test_sort_imports_targets(self):
        assert "controllers/app_controller.py" in SORT_IMPORTS_IN
