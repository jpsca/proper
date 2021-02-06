from pyceo import Cli

from .main import app
from .models import User, db


class AuthCli(Cli):
    def super(self, **kwargs):
        """Adds a superuser.

        Arguments:
        - login:
            Username
        - password:
            Plain-text password (will be encrypted)
        - name:
            Optional name

        """
        print("Adding superuser")
        kwargs["super"] = True
        User.new(**kwargs)

    def user(self, **kwargs):
        """Adds a regular user.

        Arguments:
        - login:
            Username
        - password:
            Plain-text password (will be encrypted)
        - name:
            Optional name
        """
        print("Adding user")
        User.new(**kwargs)

    def users(self):
        """List all the available users."""
        users = db.query(User).order_by(User.id)
        for user in users:
            print(user)


class Manager(app.cli.ApplicationCli):
    """Application-specific commands."""

    auth = AuthCli


manager = Manager()


def run():
    manager()
