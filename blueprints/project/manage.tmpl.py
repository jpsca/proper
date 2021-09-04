#!/usr/bin/env python
from pyceo import Cli

from [[ app_name ]].main import app
from [[ app_name ]].models import User, alembic


class AuthCli(Cli):
    def user(self, super=False, **kw):
        """
        Adds an user.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
          - name:     Optional name
          - super:    Super user?
        """
        if super:
            print("Adding superuser")
        else:
            print("Adding user")
        User.create(super=super, **kw)


app.cli.auth = AuthCli
app.cli.db = alembic.get_pyceo_cli()


if __name__ == "__main__":
    app.cli()
