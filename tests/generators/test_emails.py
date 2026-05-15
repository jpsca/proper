import pytest

from proper.generators.email import gen_email


APP_NAME = "myapp"


@pytest.fixture()
def app_in_tmp(tmp_path, app):
    """Set up a temporary app root with the emails/ and views/emails/
    directories pre-created, then point the app fixture at it."""
    app_root = tmp_path / APP_NAME
    emails_dir = app_root / "emails"
    emails_dir.mkdir(parents=True)
    (emails_dir / "__init__.py").write_text("")

    views_dir = app_root / "views" / "emails"
    views_dir.mkdir(parents=True)

    app.root_path = app_root
    app.name = APP_NAME
    return app


def _email_text(app, name_snake: str) -> str:
    return (app.root_path / "emails" / f"{name_snake}_email.py").read_text()


def _init_text(app) -> str:
    return (app.root_path / "emails" / "__init__.py").read_text()


def _view_text(app, name_snake: str) -> str:
    return (app.root_path / "views" / "emails" / f"{name_snake}.jx").read_text()


class TestGenEmail:
    def test_generates_email_class(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        text = _email_text(app_in_tmp, "welcome")
        assert "class WelcomeEmail(BaseEmail):" in text

    def test_generates_html_template(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        text = _view_text(app_in_tmp, "welcome")
        assert "Layout" in text
        assert "subject" in text

    def test_appends_to_init(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        init = _init_text(app_in_tmp)
        assert "from .welcome_email import WelcomeEmail" in init

    def test_name_inflection_from_snake(self, app_in_tmp):
        gen_email(app_in_tmp, "password_reset")
        text = _email_text(app_in_tmp, "password_reset")
        assert "class PasswordResetEmail(BaseEmail):" in text

    def test_name_inflection_from_pascal(self, app_in_tmp):
        gen_email(app_in_tmp, "OrderConfirmation")
        text = _email_text(app_in_tmp, "order_confirmation")
        assert "class OrderConfirmationEmail(BaseEmail):" in text

    def test_email_class_has_subject(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        text = _email_text(app_in_tmp, "welcome")
        assert 'subject = ""' in text

    def test_email_class_imports_base(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        text = _email_text(app_in_tmp, "welcome")
        assert "from .base_email import BaseEmail" in text

    def test_multiple_emails_append_to_init(self, app_in_tmp):
        gen_email(app_in_tmp, "Welcome")
        gen_email(app_in_tmp, "PasswordReset")
        init = _init_text(app_in_tmp)
        assert "from .welcome_email import WelcomeEmail" in init
        assert "from .password_reset_email import PasswordResetEmail" in init
