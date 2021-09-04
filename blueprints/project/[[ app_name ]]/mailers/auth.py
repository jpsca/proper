from ..app import app, send_email
from ..config import config


__all__ = (
    "render_password_reset_email",
    "send_password_reset_email",
)


def render_password_reset_email(user):
    token = user.get_timestamped_token()
    validate_url = app.url_for("Auth.reset_validate", token=token)
    reset_url = app.url_for("Auth.reset")
    return app.render(
        "emails/password_reset.html.jinja",
        validate_url=f"{config.host}{validate_url}",
        reset_url=f"{config.host}{reset_url}",
    )


def send_password_reset_email(user):
    kw = {
        "to": user.email,
        "subject": "Reset your password",
        "html": render_password_reset_email(user),
    }
    send_email(**kw)
