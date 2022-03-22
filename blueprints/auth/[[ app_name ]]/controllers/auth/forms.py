import proper.forms as f

from .validators import (
    login_exists,
    password_hasnt_been_pwned,
    password_is_long_enough,
    password_confirmed,
)


class SignInForm(f.Form):
    login = f.Text(login_exists, required=True)
    password = f.Password(required=True)


class PasswordResetForm(f.Form):
    login = f.Text(login_exists, required=True)


class PasswordChangeForm(f.Form):
    # This is a `Text` field and not a `Password` so the password is remembered
    # when the validation fails, so it can be fixed quickly.
    password = f.Text(
        password_is_long_enough,
        password_confirmed,
        password_hasnt_been_pwned,
        multiple=True,
        required=True,
    )
