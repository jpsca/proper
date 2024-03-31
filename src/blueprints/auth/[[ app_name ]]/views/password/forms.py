import typing as t

from fodantic import formable
from pydantic import BaseModel, BeforeValidator, SecretStr, model_validator

from .validators import (
    login_exists,
    password_hasnt_been_pwned,
    password_is_long_enough,
    passwords_match,
)


@formable
class PasswordResetModel(BaseModel):
    login: t.Annotated[str, BeforeValidator(login_exists)]


@formable
class PasswordChangeModel(BaseModel):
    password1: t.Annotated[
        SecretStr,
        BeforeValidator(password_is_long_enough),
    ]
    password2: SecretStr

    @model_validator(mode="after")
    def check_passwords_match(self) -> t.Self:
        pw1 = self.password1.get_secret_value()
        pw2 = self.password2.get_secret_value()

        passwords_match(pw1, pw2)
        password_hasnt_been_pwned(pw1)
        return self
