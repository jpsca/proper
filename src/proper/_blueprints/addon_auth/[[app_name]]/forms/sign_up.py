from proper import forms as f

from .auth import validators as v


class SignUpForm(f.Form):
    class Meta:
        messages = v.MESSAGES

    login = f.TextField(
        messages={"required": "Please write your email"},
    )
    password1 = f.TextField(
        messages={"required": "Please write your password"},
    )
    password2 = f.TextField(
        messages={"required": "Please repeat your password"},
    )

    def validate_login(self, value):
        v.login_is_available(value)
        return value

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
