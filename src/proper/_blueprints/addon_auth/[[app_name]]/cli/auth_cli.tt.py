from getpass import getpass

from proper_cli import Cli as CLI

from ..main import app


class AuthCLI(CLI):
    def user(self, login: str = "", password: str = "") -> None:
        """
        Adds an user.

        Login and password can be passed as arguments or will be
        prompted if not provided.

        Arguments:
            login:
                Username
            password:
                Plain-text password (will be encrypted)

        """
        from ..models.user import User

        while not login:
            login = input("Login: ")
        while True:
            while not password:
                password = getpass("Password: ")
            try:
                User.create(login=login, password=password)
                break
            except Exception as e:
                print("ERROR:", e)
                password= ""

        print("User added")

    def password(self, login: str, password: str = "") -> None:
        """
        Set the password of a user.

        It can be passed as an argument or will be prompted if not provided.

        Arguments:
            login:
                Username
            password:
                Plain-text password (will be encrypted)

        """
        from ..models.user import User

        user = User.get_by_login(login)
        if not user:
            print("User not found")
            return
        while True:
            while not password:
                password = getpass("Password: ")
            try:
                User.create(login=login, password=password)
                break
            except Exception as e:
                print("ERROR:", e)
                password= ""
        print("Password updated")


app.CLI.auth = AuthCLI  # type: ignore
