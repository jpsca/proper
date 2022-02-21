from proper.cli import Cli

from .app import app, db
from .models import User


class AuthCli(Cli):
    def user(self, login, password):
        """
        Adds an user.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
        """
        db.s.create(User, login=login, password=password)
        db.s.commit()
        print("User added")

    def password(self, login, password):
        """
        Set the password of a user.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
        """
        user = User.by_login(login)
        if not user:
            print ("User not found")
            return
        user.password = password
        db.s.commit()
        print("Password updated")


app.cli.auth = AuthCli
