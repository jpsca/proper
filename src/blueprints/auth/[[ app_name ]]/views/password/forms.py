import typing as t

from fodantic import as_form
from pydantic import BaseModel, BeforeValidator, model_validator

from .validators import (
    login_exists,
    password_hasnt_been_pwned,
    password_is_long_enough,
)


@as_form
class PasswordResetForm(BaseModel):
    login: t.Annotated[str, BeforeValidator(login_exists)]


NewPassword = t.Annotated[
    str,  # Not a `SecretStr` to make it easier to fix typos
    BeforeValidator(password_is_long_enough),
    BeforeValidator(password_hasnt_been_pwned),
]


@as_form
class PasswordChangeForm(BaseModel):
    password1: NewPassword
    password2: NewPassword

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordChangeModel":
        pw1 = self.password1
        pw2 = self.password2
        if pw1 is not None and pw2 is not None and pw1 != pw2:
            raise ValueError("Passwords don't match.<br>Remember that are case-sensitive")
        return self
