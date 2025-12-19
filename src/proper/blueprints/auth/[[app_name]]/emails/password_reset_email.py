from ..main import app, config
from .base_email import BaseEmail


class PasswordResetEmail(BaseEmail):
    subject = "Reset your password"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        token = user.get_token()
        validate_url = app.url_for("PasswordReset.edit", token=token)
        reset_url = app.url_for("PasswordReset.new")
        self.body = app.catalog.render(
            "emails/password_reset.jinja",
            validate_url=f"{config.PROTOCOL}://{config.HOST}{validate_url}",
            reset_url=f"{config.PROTOCOL}://{config.HOST}{reset_url}",
        )
        self.generate_text_alternative()
