import formidable as f

from .auth import validators as v


# The form tells the user if the login doesn't exists
# To go back to a generic "If your user exists we will send you an email"
# message, edit the "views/password_reset/create.jinja" component,
# and comment the (A) method below.


class PasswordResetForm(f.Form):
    class Meta:
        messages = v.MESSAGES

    login = f.TextField(
        messages={"required": "Please write your email"},
    )

    def validate_login(self, value):
        v.login_exists(value)  # (A)
        return value


class PasswordChangeForm(f.Form):
    class Meta:
        messages = v.MESSAGES

    password1 = f.TextField(
        messages={"required": "Please write your new password"},
    )
    password2 = f.TextField(
        messages={"required": "Please repeat your new password"},
    )

    def validate_password1(self, value):
        v.password_is_long_enough(value)
        v.password_hasnt_been_pwned(value)
        return value

    def after_validate(self) -> bool:
        password1 = self.password1.value
        password2 = self.password2.value
        if password1 != password2:
            self.password2.error = v.ERROR_PASSWORDS_MISMATCH
            return False
        return True
