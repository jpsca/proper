import hyperform as f

from [[ app_name ]].config import config
from [[ app_name ]].models import User
from .pwned import get_pwned_count


def login_exists(values):
    # msg = "We don't recognize that email. Want to try another?"
    msg = "Wrong username and/or password"
    if not values:
        return False, msg
    if not User.by_login(values[0]):
        return False, msg
    return True


def login_is_free(values):
    msg = "That email is already in use by an account"
    if not values:
        return False, msg
    if User.by_login(values[0]):
        return False, msg
    return True


password_is_long = f.LongerThan(
    config.auth_password_minlen,
    f"Your password must be at least {config.auth_password_minlen} characters long",
)


def password_hasnt_been_pwned(values):
    msg = (
        "This password may have been compromised on another site.<br>"
        "For your own safety, we recommend you create a new, unique password"
        " using something like LastPass or 1Password."
    )
    for value in values:
        if get_pwned_count(value):
            return False, msg
    return True


class SignInForm(f.Form):
    login = f.Text(login_exists, required=True)
    password = f.Password(required=True)


class PasswordResetForm(f.Form):
    login = f.Text(login_exists, required=True)


class PasswordChangeForm(f.Form):
    # I want the passwords to be remembered if there is
    # a validation error, so it can be fixed quickly.
    password = f.Text(
        f.Confirmed("Passwords don’t match.<br>Remember that are case-sensitive"),
        password_is_long,
        password_hasnt_been_pwned,
        multiple=True,
        required=True,
    )
