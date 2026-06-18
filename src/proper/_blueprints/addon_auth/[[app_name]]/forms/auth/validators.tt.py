from [[app_name]].main import config
from [[app_name]].models import User
from .pwned import get_pwned_count


ERROR_LOGIN = "login"
ERROR_LOGIN_TAKEN = "login-taken"
ERROR_PASSWORD = "password"
ERROR_AUTH = "auth"
ERROR_NEW_PASSWORD_PWNED = "new-password-pwned"
ERROR_CURRENT_PASSWORD_PWNED = "current-password-pwned"
ERROR_PASSWORD_TOO_SHORT = "password-too-short"
ERROR_PASSWORDS_MISMATCH = "passwords-mismatch"

MESSAGES = {
    ERROR_LOGIN: "We don't recognize that username. Want to try&nbsp;another?",
    ERROR_LOGIN_TAKEN: "This username is already registered.",
    ERROR_PASSWORD: (
      "Password doesn't match the username.<br>"
      "Remember that passwords are case-sensitive."
    ),
    ERROR_AUTH: (
      "Invalid username and/or password.<br>"
      "Remember that passwords are case-sensitive."
    ),
    ERROR_NEW_PASSWORD_PWNED: (
        "This password is too easy to guess and cannot be&nbsp;used.<br>"
        "Please choose a new, unique&nbsp;password."
    ),
    ERROR_CURRENT_PASSWORD_PWNED: (
        "This password has become too easy to guess and can no longer be&nbsp;used.<br>"
        "Please choose a new, unique&nbsp;password."
    ),
    ERROR_PASSWORD_TOO_SHORT: "Your password must be at least {minlen} characters&nbsp;long",
    ERROR_PASSWORDS_MISMATCH: "Passwords don't match. Remember that passwords are case-sensitive.",
}


def login_exists(login: str):
    if not login or not User.get_by_login(login):
        raise ValueError(ERROR_LOGIN)


def login_is_available(login: str):
    if login and User.get_by_login(login):
        raise ValueError(ERROR_LOGIN_TAKEN)


def password_is_long_enough(password: str):
    if len(password) < int(config.AUTH_PASSWORD_MINLEN):
        raise ValueError(
            ERROR_PASSWORD_TOO_SHORT,
            {"minlen": config.AUTH_PASSWORD_MINLEN}
        )


def password_hasnt_been_pwned(password: str):
    if get_pwned_count(password) > 0:
        raise ValueError(ERROR_NEW_PASSWORD_PWNED)
