from proper_cli import Cli

from ..app import app
from ..models import User


class AuthCli(Cli):
    def user(self, login: str, password: str) -> None:
        """
        Adds an user.

        Args:
            login:    Username
            password: Plain-text password (will be encrypted)

        """
        User.create(login=login, password=password)
        print("User added")

    def password(self, login: str, password: str) -> None:
        """
        Set the password of a user

        Args:
            login:    Username
            password: Plain-text password (will be encrypted)

        """
        user = User.get_by_login(login)
        if not user:
            print("User not found")
            return
        user.set_password(password)
        user.save()
        print("Password updated")


app.Cli.auth = AuthCli
