from [[ app_name ]].app import app, auth, config
from .mailer import send_email


__all__ = (
    "render_password_reset_email",
    "send_password_reset_email",
)


def render_password_reset_email(user):
    token = auth.get_timestamped_token(user)
    validate_url = app.url_for("PasswordResets.edit", pk=token)
    reset_url = app.url_for("PasswordResets.new")
    return app.catalog.render(
        "Emails.PasswordResets",
        validate_url=f"{config.PROTOCOL}://{config.HOST}{validate_url}",
        reset_url=f"{config.PROTOCOL}://{config.HOST}{reset_url}",
    )


def send_password_reset_email(user):
    kw = {
        "to": user.email,
        "subject": "Reset your password",
        "html": render_password_reset_email(user),
    }
    send_email(**kw)
