from ..main import app, config
from .email_message import EmailMessage


class PasswordResetEmail(EmailMessage):
    subject = "Reset your password"

    def __init__(self, user, **kwargs):
        super().__init__(**kwargs)
        token = user.get_token()
        validate_url = app.url_for("PasswordReset.edit", pk=token)
        reset_url = app.url_for("PasswordReset.new")
        self.body = app.catalog.render(
            "emails/password_reset.jinja",
            validate_url=f"{config.PROTOCOL}://{config.HOST}{validate_url}",
            reset_url=f"{config.PROTOCOL}://{config.HOST}{reset_url}",
        )
        self.generate_text_alternative()
