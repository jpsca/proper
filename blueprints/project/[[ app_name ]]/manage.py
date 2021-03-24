"""
Application-specific CLI commands for `bin/manage`
"""
from liquid_orm import commands as lc
from pyceo import Cli

from .main import app
from .models import User, db


class AuthCli(Cli):
    def super(self, **kwargs):
        """
        Adds a superuser.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
          - name:     Optional name

        """
        print("Adding superuser")
        kwargs["super"] = True
        User.create(**kwargs)

    def user(self, **kwargs):
        """
        Adds a regular user.

        Arguments:
          - login:    Username
          - password: Plain-text password (will be encrypted)
          - name:     Optional name

        """
        print("Adding user")
        User.create(**kwargs)

    def users(self):
        """
        List all the available users.
        """
        for user in User.order_by("id").all():
            print(user)


MIGRATIONS_PATH = str((app.root_path / ".." / "db" / "migrations").resolve())


class DBCli(Cli):
    def create(self, name, *, table=None, create=False):
        """
        Create a new migration file.

        Arguments:
          - name:             The name of the migration.
          - table [optional]: The table to create the migration for.
          - create [False]:   Whether the migration will create the table or not.

        """
        lc.create(db, name, path=MIGRATIONS_PATH, table=table, create=create)

    def migrate(self, database=None, *, pretend=False):
        """
        Run the database migrations.

        Arguments:
          - database: The database connection to use.
          - pretend: Only print the SQL queries that would be run.

        """
        lc.migrate(db, database=database, path=MIGRATIONS_PATH, pretend=pretend)

    def rollback(self, database=None, *, pretend=False):
        """
        Rollback the last database migration.

        Arguments:
          - database: The database connection to use.
          - pretend: Only print the SQL queries that would be run.

        """
        lc.rollback(db, database=database, path=MIGRATIONS_PATH, pretend=pretend)

    def reset(self, database=None, *, pretend=False):
        """
        Rollback all database migrations.

        Arguments:
          - database: The database connection to use.
          - pretend: Only print the SQL queries that would be run.

        """
        lc.reset(db, database=database, path=MIGRATIONS_PATH, pretend=pretend)

    def status(self, database=None):
        """
        Show a list of migrations up/down.

        Arguments:
          - database: The database connection to use.

        """
        lc.status(db, database=database, path=MIGRATIONS_PATH)


class Manager(app.cli.ApplicationCli):
    """Application-specific commands."""

    auth = AuthCli
    db = DBCli


manager = Manager()
run = manager
