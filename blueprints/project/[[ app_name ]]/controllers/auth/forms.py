import proper_forms as f

from .validators import (
    login_exists,
    password_hasnt_been_pwned,
    password_is_long,
)


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
