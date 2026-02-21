"""Tests for proper.install.auth — installs auth blueprint into an app."""

import pytest

from proper.install.auth import SORT_IMPORTS_IN, install


APP_NAME = "myapp"

# Minimal app_controller.py that add_to_concerns can parse
APP_CONTROLLER = """\
from proper.controller import Controller


class AppController(
    Controller,
):
    pass
"""


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the files that the auth blueprint
    expects to already exist (append/prepend targets and sort_imports_in targets)."""
    app_root = tmp_path / APP_NAME

    # Directories
    for d in (
        "controllers",
        "cli",
        "config",
        "emails",
        "forms",
        "models",
        "views/common",
        "views/pages",
    ):
        (app_root / d).mkdir(parents=True)

    # Pre-existing files that .append/.prepend files target
    (app_root / "controllers" / "app_controller.py").write_text(APP_CONTROLLER)
    (app_root / "main.py").write_text("from proper import App\napp = App(__name__)\n")
    (app_root / "cli" / "__init__.py").write_text("")
    (app_root / "config" / "__init__.py").write_text("")
    (app_root / "emails" / "__init__.py").write_text("")
    (app_root / "models" / "__init__.py").write_text("")
    (app_root / "router.py").write_text("from proper.router import Router\nrouter = Router()\n")
    (app_root / "views" / "common" / "nav.jinja").write_text("<nav></nav>\n")

    app.root_path = app_root
    app.name = APP_NAME
    return app


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------


class TestFileCreation:
    def test_creates_authentication_concern(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "controllers" / "concerns" / "authentication.py"
        assert path.exists()

    def test_creates_session_controller(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "controllers" / "session_controller.py"
        assert path.exists()

    def test_creates_password_reset_controller(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "controllers" / "password_reset_controller.py"
        assert path.exists()

    def test_creates_user_model(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "models" / "user.py"
        assert path.exists()

    def test_creates_session_model(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "models" / "session.py"
        assert path.exists()

    def test_creates_authenticable_concern(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "models" / "concerns" / "authenticable.py"
        assert path.exists()

    def test_creates_session_form(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "forms" / "session.py"
        assert path.exists()

    def test_creates_password_reset_form(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "forms" / "password_reset.py"
        assert path.exists()

    def test_creates_auth_form_validators(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "forms" / "auth" / "validators.py"
        assert path.exists()

    def test_creates_auth_config(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "config" / "auth.py"
        assert path.exists()

    def test_creates_auth_cli(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "cli" / "auth_cli.py"
        assert path.exists()

    def test_creates_password_reset_email(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "emails" / "password_reset_email.py"
        assert path.exists()

    def test_creates_session_view(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "views" / "pages" / "session" / "new.jinja"
        assert path.exists()

    def test_creates_password_reset_views(self, app_in_tmp):
        install(app_in_tmp)
        views = app_in_tmp.root_path / "views" / "pages" / "password_reset"
        assert (views / "new.jinja").exists()
        assert (views / "edit.jinja").exists()
        assert (views / "show.jinja").exists()
        assert (views / "invalid.jinja").exists()

    def test_creates_auth_layout(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "views" / "layouts" / "auth.jinja"
        assert path.exists()

    def test_creates_auth_css(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "assets" / "styles" / "auth.css"
        assert path.exists()

    def test_creates_password_reset_email_template(self, app_in_tmp):
        install(app_in_tmp)
        path = app_in_tmp.root_path / "views" / "emails" / "password_reset.jinja"
        assert path.exists()


# ---------------------------------------------------------------------------
# Appended / prepended content
# ---------------------------------------------------------------------------


class TestAppendedContent:
    def test_appends_to_main(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "main.py").read_text()
        assert "auth = app.auth" in text

    def test_appends_to_config_init(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "config" / "__init__.py").read_text()
        assert "from .auth import *" in text

    def test_appends_to_emails_init(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "emails" / "__init__.py").read_text()
        assert "PasswordResetEmail" in text

    def test_appends_to_models_init(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "models" / "__init__.py").read_text()
        assert "from .user import User" in text
        assert "from .session import Session" in text

    def test_appends_to_router(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "router.py").read_text()
        assert "auth_router" in text

    def test_appends_to_nav(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "views" / "common" / "nav.jinja").read_text()
        assert "Sign out" in text
        assert "Sign in" in text

    def test_prepends_to_cli_init(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "cli" / "__init__.py").read_text()
        assert "auth_cli" in text

    def test_prepends_to_app_controller(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        assert "from .concerns.authentication import Authentication" in text


# ---------------------------------------------------------------------------
# add_to_concerns
# ---------------------------------------------------------------------------


class TestConcerns:
    def test_adds_authentication_concern(self, app_in_tmp):
        install(app_in_tmp)
        text = (app_in_tmp.root_path / "controllers" / "app_controller.py").read_text()
        assert "Authentication," in text


# ---------------------------------------------------------------------------
# sort_imports_in
# ---------------------------------------------------------------------------


class TestSortImports:
    def test_sort_imports_targets(self):
        assert "main.py" in SORT_IMPORTS_IN
        assert "controllers/app_controller.py" in SORT_IMPORTS_IN
        assert "cli/__init__.py" in SORT_IMPORTS_IN
        assert "emails/__init__.py" in SORT_IMPORTS_IN
