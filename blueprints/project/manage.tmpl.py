#!/usr/bin/env python
from pyceo import Cli

from [[ app_name ]].main import app
from [[ app_name ]].models import User, alembic, dbs


class AuthCli(Cli):
    def user(self, login, password):
        """
        Adds an user.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
        """
        dbs.create(User, login=login, password=password)
        dbs.commit()
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
        dbs.commit()
        print("Password updated")


app.cli.auth = AuthCli
app.cli.db = alembic.get_pyceo_cli()


if __name__ == "__main__":
    app.cli()
