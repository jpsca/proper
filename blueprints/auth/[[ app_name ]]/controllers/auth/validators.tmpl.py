import proper.forms as f

from [[ app_name ]].app import config
from [[ app_name ]].models import User
from .pwned import get_pwned_count


ERROR_CREDENTIALS = "Wrong username and/or password"

# ERROR_LOGIN = "We don't recognize that email. Want to try another?"
ERROR_LOGIN = ERROR_CREDENTIALS

ERROR_EMAIL_IN_USE = "That email is already in use by an account"

ERROR_PASSWORD_TOO_SHORT = f"Your password must be at least {config.auth.password_minlen} characters long"

ERROR_PASSWORD_PWNED =  (
    "This password may have been compromised on another site.<br>"
    "For your own safety, we recommend you create a new, unique password"
    " using something like LastPass or 1Password."
)

ERROR_PASSWORD_UNCONFIRMED = "Passwords don't match.<br>Remember that are case-sensitive"


def login_exists(values):
    if not values:
        return False, ERROR_LOGIN
    if not User.exists(values[0]):
        return False, ERROR_LOGIN
    return True


def login_is_free(values):
    if not values:
        return False, ERROR_EMAIL_IN_USE
    if User.exists(values[0]):
        return False, ERROR_EMAIL_IN_USE
    return True


def password_hasnt_been_pwned(values):
    for value in values:
        if get_pwned_count(value):
            return False, ERROR_PASSWORD_PWNED
    return True


password_is_long_enough = f.LongerThan(config.auth.password_minlen, ERROR_PASSWORD_TOO_SHORT)
password_confirmed = f.Confirmed(ERROR_PASSWORD_UNCONFIRMED)
