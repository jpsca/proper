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
        try:
            User.create(login=login, password=password)
        except Exception as e:
            print("ERROR:", e)
            return
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
        try:
            user.set_password(password)
            user.save()
        except Exception as e:
            print("ERROR:", e)
            return
        print("Password updated")


app.Cli.auth = AuthCli
