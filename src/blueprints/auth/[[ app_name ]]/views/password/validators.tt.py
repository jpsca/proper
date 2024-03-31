from pydantic_core import PydanticCustomError

from .pwned import get_pwned_count
from [[ app_name ]].app import config
from [[ app_name ]].models import User


ERROR_LOGIN = "We don't recognize that username. Want to try&nbsp;another?"

ERROR_PASSWORD_PWNED = (
    "This password may have been compromised on another&nbsp;site.<br>"
    "For your own safety, we recommend you create a new, unique password,"
    " ideally using something like 1Password or&nbsp;LastPass."
)

ERROR_PASSWORD_TOO_SHORT = "Your password must be at least {minlen} characters&nbsp;long"

ERROR_PASSWORDS_MISMATCH = "Passwords don't match.<br>Remember that are case-sensitive"


def login_exists(login: str) -> str:
    if not login or not User.get_by_login(login):
        raise PydanticCustomError("login", ERROR_LOGIN)
    return login


def password_is_long_enough(password: str) -> str:
    if len(password) < int(config.AUTH_PASSWORD_MINLEN):
        raise PydanticCustomError(
            "password-too-short",
            ERROR_PASSWORD_TOO_SHORT,
            {"minlen": config.AUTH_PASSWORD_MINLEN}
        )
    return password


def password_hasnt_been_pwned(password: str) -> str:
    if get_pwned_count(password):
        raise PydanticCustomError("password-pwned", ERROR_PASSWORD_PWNED)
    return password


def passwords_match(pw1: str, pw2: str):
    if pw1 != pw2:
        raise PydanticCustomError(
            "password-confirmation",
            ERROR_PASSWORDS_MISMATCH
        )
