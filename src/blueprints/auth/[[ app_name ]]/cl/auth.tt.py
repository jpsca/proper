from proper_cli import Cli

from [[ app_name ]].app import app


class AuthCL(Cli):
    def user(self, login: str, password: str) -> None:
        """
        Adds an user.

        Arguments:

        - login:
            Username

        - password:
            Plain-text password (will be encrypted)

        """
        from [[ app_name ]].models.user import User

        try:
            User.create(login=login, password=password)
        except Exception as e:
            print("ERROR:", e)
            return
        print("User added")

    def password(self, login: str, password: str) -> None:
        """
        Set the password of a user

        Arguments:

        - login:
            Username

        - password:
            Plain-text password (will be encrypted)

        """
        from [[ app_name ]].models.user import User

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


app.CL.auth = AuthCL
