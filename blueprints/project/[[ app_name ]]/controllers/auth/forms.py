import hyperform as hf

from .validators import (
    login_exists,
    password_hasnt_been_pwned,
    password_is_long,
)


class SignInForm(hf.Form):
    login = hf.Text(login_exists, required=True)
    password = hf.Password(required=True)


class PasswordResetForm(hf.Form):
    login = hf.Text(login_exists, required=True)


class PasswordChangeForm(hf.Form):
    password = hf.Text(
        hf.Confirmed("Passwords don’t match.<br>Remember that are case-sensitive"),
        password_is_long,
        password_hasnt_been_pwned,
        multiple=True,
        required=True,
    )
