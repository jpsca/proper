from fodantic import as_form
from pydantic import BaseModel, SecretStr, model_validator

from [[ app_name ]].models import User
from ..password.validators import login_exists  # (A)


# The form tells the user if the login doesn't exists or the password is wrong
# To go back to a generic "Invalid username and/or password" message,
# comment the (A) lines and un-comment the (B) lines

@as_form
class SignInModel(BaseModel):
    login: t.Annotated[str, BeforeValidator(login_exists)]  # (A)
    # login: str  # (B)
    password: SecretStr

    @model_validator(mode="after")
    def authenticate(self) -> self:
        user = User.authenticate(login=self.login, password=self.password)
        if not user:
            raise ValueError("Wrong password")  # (A)
            # raise ValueError("Wrong username and/or password")  # (B)
        return self
