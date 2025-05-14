from pydantic_core import PydanticCustomError

from .pwned import get_pwned_count
from app.main import config
from app.models import User


ERROR_LOGIN = "We don't recognize that username. Want to try&nbsp;another?"

ERROR_NEW_PASSWORD_PWNED = (
    "This password is too easy to guess and cannot be&nbsp;used.<br>"
    "Please choose a new, unique&nbsp;password."
)

ERROR_CURRENT_PASSWORD_PWNED = (
    "This password has become too easy to guess and can no longer be&nbsp;used.<br>"
    "Please choose a new, unique&nbsp;password."
)

ERROR_PASSWORD_TOO_SHORT = "Your password must be at least {minlen} characters&nbsp;long"

ERROR_PASSWORDS_MISMATCH = "Passwords don't match.<br>Remember that arecase-sensitive"


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


def password_has_been_pwned(password: str) -> bool:
    return get_pwned_count(password) > 0


def password_hasnt_been_pwned(password: str) -> str:
    if password_has_been_pwned(password):
        raise PydanticCustomError("password-pwned", ERROR_NEW_PASSWORD_PWNED)
    return password


def passwords_match(pw1: str, pw2: str):
    if pw1 != pw2:
        raise PydanticCustomError(
            "password-confirmation",
            ERROR_PASSWORDS_MISMATCH
        )
