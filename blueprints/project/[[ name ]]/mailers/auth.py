from [[ name ]].app import app
from [[ name ]].config import config
from [[ name ]].jobs.emails import send_email
from [[ name ]].adapters import queue_notif


__all__ = (
    "render_password_reset_email",
    "send_password_reset_email",
)


def render_password_reset_email(user):
    token = user.get_timestamped_token()
    validate_url = app.url_for("Auth.reset_validate", token=token)
    reset_url = app.url_for("Auth.reset")
    return app.render(
        "emails/password_reset.html",
        validate_url=f"{config.host}{validate_url}",
        reset_url=f"{config.host}{reset_url}",
    )


def send_password_reset_email(user):
    kwargs = {
        "to": user.email,
        "subject": "Reset your password",
        "html": render_password_reset_email(user),
    }
    if config.debug:
        send_email(**kwargs)
    else:
        queue_notif.enqueue(send_email, **kwargs)
