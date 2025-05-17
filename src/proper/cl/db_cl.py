import sys
from importlib import import_module
from pathlib import Path

import peewee as pw
from peewee_migrate import Router as PWRouter
from proper_cli import Cli


QUEUE = "proper_queue"
CACHE = "proper_cache"


def get_db_cl(app):
    class DBCL(Cli):
        def _get_db(self, name: str, validate: bool = True) -> pw.Database | None:
            """Get the database instance for the given name.

            If the database is not found, it will print an error message (unless `validate` is False)
            and return None.
            """
            log = print if validate is True else (lambda *args, **kwargs: None)

            db = app.db.get(name)
            if db is None:
                log(f"Database '{name}' not found.")
                return

            if name == QUEUE:
                dburi = app.config.QUEUE.get("database")
            elif name == CACHE:
                dburi = app.config.CACHE.get("database")
            else:
                dburi = app.config.DATABASES.get(name, {}).get("database")

            if dburi == ":memory:":
                log(f"{name}: Cannot run migrations on in-memory database.")
                return

            return db

        def _get_router(self, name: str, validate: bool = True) -> PWRouter | None:
            db = self._get_db(name, validate=validate)
            if db is None:
                if validate:
                    sys.exit(0)
                return

            if db.is_closed():
                db.connect()
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
            if QUEUE == db:
                models = getattr(app.queue, "models", None)
            elif CACHE == db:
                models = getattr(app.cache, "models", None)
            else:
                models = import_module("app.models")

            if not models:
                print("No models found.")
                sys.exit(0)

            router = self._get_router(db)
            assert router
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
                assert router
                if not router.diff:
                    print("No pending migrations found.")
                    return
                done = router.run(fake=fake)
                for migration in done:
                    print(f"{router.migrate_dir}/{migration}.py")
                return

            # Run all migrations for all databases
            found = False
            for name in [*app.config.DATABASES.keys(), QUEUE, CACHE]:
                router = self._get_router(name, validate=False)
                if router is None or not router.diff:
                    continue

                found = True
                print(f"Running migrations for '{name}':")
                done = router.run(fake=fake)
                for migration in done:
                    print(f"{router.migrate_dir}/{migration}.py")
                print()

            if not found:
                print("No pending migrations found.")

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
            assert router
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
            assert router
            router.rollback()

        def merge(self, name: str = "initial", db: str = "main"):
            """Merge all migrations into one.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            assert router
            router.merge(name)

        def todo(self, db: str = "main"):
            """Show all migrations that have not been applied.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            assert router
            for migration in router.todo:
                print(f"{router.migrate_dir}/{migration}.py")

        def done(self, db: str = "main"):
            """Show all migrations that have been applied.

            Arguments:

            - db:
                Target database name to. Default is "main".

            """
            router = self._get_router(db)
            assert router
            for migration in router.done:
                print(f"{router.migrate_dir}/{migration}.py")

    return DBCL
