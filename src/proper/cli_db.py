from peewee_moves import DatabaseManager
from proper_cli import Cli


def get_cli_db(app):
    manager = DatabaseManager(app.db, directory="db/migrations")

    class DB(Cli):
        def info(self):
            """Show the current database.

            Don't include any sensitive information like passwords."""
            return manager.info()

        def status(self) -> bool:
            """
            Show all the migrations and a status for each.

            Return:
                True if listing was successful, otherwise False.
            """
            return manager.status() or False

        def delete(self, migration: str) -> bool:
            """Delete the migration from filesystem and database.

            As if it never happened.

            Args:
                migration: Name of migration to find (not including extension).

            Return:
                True if delete was successful, otherwise False.
            """
            return manager.delete(migration)

        def upgrade(self, target: str = "", fake: bool = False) -> bool:
            """Run all the migrations (up to target if specified).

            If no target, run all upgrades.

            Args:
                target: Migration target to limit upgrades.
                fake: Should the migration actually run?.

            Return:
                True if upgrade was successful, otherwise False.
            """
            return manager.upgrade(target=target or None, fake=fake)

        def downgrade(self, target: str = "", fake: bool = False) -> bool:
            """Run all the migrations (down to target if specified).

            If no target, run one downgrade.

            Args:
                target: Migration target to limit downgrades.
                fake: Should the migration actually run?.

            Return:
                True if downgrade was successful, otherwise False.
            """
            return manager.downgrade(target=target or None, fake=fake)

        def revision(self, name: str = "auto") -> bool:
            """Create a single blank migration file with given name
            or default of 'auto'.

            Args:
                name: Name of migration to create (default auto migration).

            Return:
                True if migration file was created, otherwise False.
            """
            return manager.revision(name)

        def create(self, modelstr: str) -> bool:
            """Create a new migration file for an existing model.

            Args:
                modelstr: Name of the model.

            Return:
                True if migration file was created, otherwise False.
            """
            return manager.create(modelstr)

    return DB
