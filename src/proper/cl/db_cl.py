import sys
from importlib import import_module
from pathlib import Path

from peewee_migrate import Router as PWRouter
from proper_cli import Cli


def get_db_cl(app):
    class DBCL(Cli):
        def _get_router(self, name: str) -> PWRouter:
            db = app.db.get(name) or None
            if db is None:
                print(f"Database '{name}' not found in DATABASES config.")
                sys.exit(0)
            if app.config.DATABASES[name].get("database") == ":memory:":
                print("Cannot run migrations on in-memory database.")
                sys.exit(0)
            migrate_dir = Path("db", name)
            migrate_dir.mkdir(exist_ok=True)
            return PWRouter(db, migrate_dir=migrate_dir)

        def create(self, name: str = "auto", db: str = "main"):
            """Create a new migration file for all changes in the models.

            Arguments:

            - name:
                Optional name for the migration
            - db:
                Database name to create the migration for. Default is "main".

            """
            if (app.config["QUEUE"] or {}).get("db") == db:
                models = getattr(app.queue, "models", None)
            elif (app.config["CACHE"] or {}).get("db") == db:
                models = getattr(app.cache, "models", None)
            else:
                models = import_module("app.models")

            if not models:
                print("No models found.")
                sys.exit(0)
            router = self._get_router(db)
            migration = router.create(name, auto=models)
            if migration:
                print(f"{router.migrate_dir}/{migration}.py")

        def migrate(self, fake: bool = False, db: str = ""):
            """Run/emulate all the pending migrations.

            Arguments:

            - target:
                Migration target to limit upgrades.
            - fake:
                Update migration table but don't run migration.
            - db:
                Database name to run the migration for.
                Default is "", meaning running the pending migrations
                for all databases.

            """
            if db:
                # Run all migrations for the specified database
                router = self._get_router(db)
                if not router.todo:
                    return
                done = router.run(fake=fake)
                for migration in done:
                    print(f"{router.migrate_dir}/{migration}.py")
            else:
                # Run all migrations for all databases
                for name, db in app.db.items():
                    if db is None:
                        continue
                    router = PWRouter(db, migrate_dir=f"db/{name}")
                    if not router.todo:
                        continue
                    print(f"Running migrations for '{name}':")
                    done = router.run(fake=fake)
                    for migration in done:
                        print(f"{router.migrate_dir}/{migration}.py")
                    print()

        def migrate_to(self, target: str, fake: bool = False, db: str = "main"):
            """Run/emulate all the pending migrations up to `target`.

            Arguments:

            - target:
                Migration target to limit upgrades.
            - fake:
                Update migration table but don't run migration.
            - db:
                Database name to run the migration for. Default is "main".

            """
            router = self._get_router(db)
            done = router.run(name=target, fake=fake)
            for migration in done:
                print(f"{router.migrate_dir}/{migration}.py")

        def rollback(self, db: str = "main"):
            """Rollback the latest migration.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            router.rollback()

        def merge(self, name: str = "initial", db: str = "main"):
            """Merge all migrations into one.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            router.merge(name)

        def todo(self, db: str = "main"):
            """Show all migrations that have not been applied.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            for migration in router.todo:
                print(f"{router.migrate_dir}/{migration}.py")

        def done(self, db: str = "main"):
            """Show all migrations that have been applied.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            for migration in router.done:
                print(f"{router.migrate_dir}/{migration}.py")

    return DBCL
