from importlib import import_module

from peewee_migrate import Router as PWRouter
from proper_cli import Cli

from proper.helpers.utils import get_instance


def get_db_cl(app):
    class DBCL(Cli):
        def _get_router(self) -> PWRouter:
            db_config = app.config.DATABASE.copy()
            migrate_dir = db_config.pop("migrations", "db/migrations")
            db = get_instance(**db_config)
            return PWRouter(db, migrate_dir=migrate_dir)

        def create(self, name: str = "auto"):
            """Create a new migration file for all changes in the models.

            Arguments:

            - name:
                Optional name for the migration

            """
            module = import_module(f"{app.name}.models")
            router = self._get_router()
            migration = router.create(name, auto=module)
            if migration:
                print(f"{router.migrate_dir}/{migration}.py")

        def migrate(self, target: str = "", fake: bool = False):
            """Run all the migrations (up to target if specified).

            If no target, run all upgrades.

            Arguments:

            - target:
                Migration target to limit upgrades.

            - fake:
                Update migration table but don't run migration.

            """
            router = self._get_router()
            done = router.run(name=target or None, fake=fake)
            for migration in done:
                print(f"{router.migrate_dir}/{migration}.py")

        def rollback(self):
            """Rollback the latest migration."""
            router = self._get_router()
            router.rollback()

        def todo(self):
            """Show all migrations that have not been applied."""
            router = self._get_router()
            for migration in router.todo:
                print(f"{router.migrate_dir}/{migration}.py")

        def done(self):
            """Show all migrations that have been applied."""
            router = self._get_router()
            for migration in router.done:
                print(f"{router.migrate_dir}/{migration}.py")

        def merge(self, name: str = "initial"):
            """Merge all migrations into one"""
            router = self._get_router()
            router.merge(name)

    return DBCL
