from importlib import import_module

from peewee_migrate import Router
from proper_cli import Cli


MIGRATE_DIR = "db/migrations"


def get_db_cli(app):
    class DB(Cli):
        @property
        def _router(self) -> Router:
            return Router(app.db, migrate_dir=MIGRATE_DIR)

        def create(self, name: str = "auto"):
            """Create a new migration file for all changes in the models.

            Args:
                name: Optional name for the migration
            """
            module = import_module(f"{app.name}.models")
            migration = self._router.create(name, auto=module)
            print("Created migration", f"{MIGRATE_DIR}/{migration}.py")

        def migrate(self, target: str = "", fake: bool = False):
            """Run all the migrations (up to target if specified).

            If no target, run all upgrades.

            Args:
                target: Migration target to limit upgrades.
                fake: Update migration table but don't run migration.

            """
            done = self._router.run(name=target or None, fake=fake)
            for migration in done:
                print(migration)

        def rollback(self):
            """Rollback the latest migration."""
            self._router.rollback()

        def todo(self):
            """Show all migrations that have not been applied."""
            for migration in self._router.todo:
                print(migration)

        def done(self):
            """Show all migrations that have been applied."""
            for migration in self._router.done:
                print(migration)

        def merge(self, name: str = "initial"):
            """Merge all migrations into one"""
            self._router.merge(name)

    return DB
