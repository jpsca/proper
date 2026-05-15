"""Tests for proper.install.auth — installs auth blueprint into an app."""

import pytest

from proper.install import auth


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
    (app_root / "views" / "common" / "nav.jx").write_text("<nav></nav>\n")

    app.root_path = app_root
    app.name = APP_NAME
    return app


def test_file_creation(app_in_tmp):
    auth.install(app_in_tmp)
    root_path = app_in_tmp.root_path

    # creates_authentication_concern
    path = root_path / "controllers" / "concerns" / "authentication.py"
    assert path.exists()

    # creates_session_controller
    path = root_path / "controllers" / "session_controller.py"
    assert path.exists()

    # creates_password_reset_controller
    path = root_path / "controllers" / "password_reset_controller.py"
    assert path.exists()

    # creates_user_model
    path = root_path / "models" / "user.py"
    assert path.exists()

    # creates_session_model
    path = root_path / "models" / "session.py"
    assert path.exists()

    # creates_authenticable_concern
    path = root_path / "models" / "concerns" / "authenticable.py"
    assert path.exists()

    # creates_session_form
    path = root_path / "forms" / "session.py"
    assert path.exists()

    # creates_password_reset_form
    path = root_path / "forms" / "password_reset.py"
    assert path.exists()

    # creates_auth_form_validators
    path = root_path / "forms" / "auth" / "validators.py"
    assert path.exists()

    # creates_auth_config
    path = root_path / "config" / "auth.py"
    assert path.exists()

    # creates_auth_cli
    path = root_path / "cli" / "auth_cli.py"
    assert path.exists()

    # creates_password_reset_email
    path = root_path / "emails" / "password_reset_email.py"
    assert path.exists()

    # creates_session_view
    path = root_path / "views" / "pages" / "session" / "new.jx"
    assert path.exists()

    # creates_password_reset_views
    views = root_path / "views" / "pages" / "password_reset"
    assert (views / "new.jx").exists()
    assert (views / "edit.jx").exists()
    assert (views / "show.jx").exists()
    assert (views / "invalid.jx").exists()

    # creates_auth_layout
    path = root_path / "views" / "layouts" / "auth.jx"
    assert path.exists()

    # creates_auth_css
    path = root_path / "assets" / "styles" / "auth.css"
    assert path.exists()

    # creates_password_reset_email_template
    path = root_path / "views" / "emails" / "password_reset.jx"
    assert path.exists()

    # appends_to_main
    text = (root_path / "main.py").read_text()
    assert "auth = app.auth" in text

    # appends_to_config_init
    text = (root_path / "config" / "__init__.py").read_text()
    assert "from .auth import *" in text

    # appends_to_emails_init
    text = (root_path / "emails" / "__init__.py").read_text()
    assert "PasswordResetEmail" in text

    # appends_to_models_init
    text = (root_path / "models" / "__init__.py").read_text()
    assert "from .user import User" in text
    assert "from .session import Session" in text

    # appends_to_nav
    text = (root_path / "views" / "common" / "nav.jx").read_text()
    assert "Sign out" in text
    assert "Sign in" in text

    # prepends_to_cli_init
    text = (root_path / "cli" / "__init__.py").read_text()
    assert "auth_cli" in text

    # prepends_to_app_controller
    text = (root_path / "controllers" / "app_controller.py").read_text()
    assert "from .concerns.authentication import Authentication" in text

    # adds_authentication_concern
    text = (root_path / "controllers" / "app_controller.py").read_text()
    assert "Authentication," in text
