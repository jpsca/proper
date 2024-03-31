import typing as t

from fodantic import formable
from pydantic import BaseModel, BeforeValidator, SecretStr, model_validator
from pydantic_core import PydanticCustomError

from ..password.validators import login_exists  # (A)
from [[ app_name ]].models import User


# The form tells the user if the login doesn't exists or the password is wrong
# To go back to a generic "Invalid username and/or password" message,
# comment the (A) lines and un-comment the (B) lines

@formable
class SignInModel(BaseModel):
    login: t.Annotated[str, BeforeValidator(login_exists)]  # (A)
    # login: str  # (B)
    password: SecretStr

    @model_validator(mode="after")
    def authenticate(self) -> t.Self:
        password = self.password.get_secret_value()
        user = User.authenticate(login=self.login, password=password)
        if not user:
            raise PydanticCustomError("password", "Wrong password")  # (A)
            # raise PydanticCustomError("auth", "Wrong username and/or password")  # (B)
        return self
