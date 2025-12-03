import formidable as f

from ..models import User
from .auth import validators as v


# The form tells the user if the login doesn't exists or the password is wrong
# To go back to a generic "Invalid username and/or password" message,
# comment the (A) lines and un-comment the (B) lines below.


class SignInForm(f.Form):
    class Meta:
        messages = v.MESSAGES

    login = f.TextField(
        messages={"required": "Please write your email"},
    )
    password = f.TextField(
        messages={"required": "Please write your password"},
    )

    def validate_login(self, value):
        v.login_exists(value)  # (A)
        return value

    def on_after_validation(self) -> bool:
        login = self.login.value
        password = self.password.value
        user = User.authenticate(login=login, password=password)
        if not user:
            self.password.error = v.ERROR_PASSWORD  # (A)
            # self.login.error = v.ERROR_AUTH  # (B)
            return False

        return True
