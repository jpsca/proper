import pydantic

from [[ app_name ]].app import config
from [[ app_name ]].models import User

from .pwned import get_pwned_count


ERROR_LOGIN = "We don't recognize that username. Want to try another?"

ERROR_PASSWORD_PWNED = (
    "This password may have been compromised on another site.<br>"
    "For your own safety, we recommend you create a new, unique password"
    " using something like LastPass or 1Password."
)

ERROR_PASSWORD_TOO_SHORT = f"Your password must be at least {config.AUTH_PASSWORD_MINLEN} characters long"


def login_exists(login: str) -> bool:
    if not login or not User.get_by_login(login):
        raise ValueError(ERROR_LOGIN)
    return login


def password_hasnt_been_pwned(password: str):
    if get_pwned_count(password):
        raise ValueError(ERROR_PASSWORD_PWNED)
    return password


password_is_long_enough = pydantic.Field(
    min_length=config.AUTH_PASSWORD_MINLEN,
    description=ERROR_PASSWORD_TOO_SHORT
)
