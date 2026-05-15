from ..main import app, config
from .base_email import BaseEmail


class PasswordResetEmail(BaseEmail):
    subject = "Reset your password"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        token = user.generate_token_for("password_reset")
        self.validate_url = app.url_for("PasswordReset.edit", token=token, _full=True)
        self.reset_url = app.url_for("PasswordReset.new", _full=True)
