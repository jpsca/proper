import shutil
import subprocess
import sys
from importlib import import_module
from pathlib import Path

from peewee_migrate import Router as PWRouter
from proper_cli import Cli

from ..constants import DB_CACHE, DB_QUEUE
from ..models import run_seeds


MIGRATION_TEMPLATE = '''\
"""Peewee migrations -- {name}.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    {migrate}


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    {rollback}
'''


class Router(PWRouter):
    """Router subclass that writes a leaner migration template and runs
    ruff format on the result if ruff is available.
    """

    def compile(self, name, migrate="", rollback="", num=None) -> str:
        if num is None:
            num = len(self.todo)
        name = f"{num + 1:03}_{name}"
        filename = name + ".py"
        path = self.migrate_dir / filename
        path.write_text(
            MIGRATION_TEMPLATE.format(migrate=migrate, rollback=rollback, name=filename)
        )
        _ruff_format(path)
        return name


def _ruff_format(path: Path) -> None:
    ruff = shutil.which("ruff")
    if not ruff:
        return
    try:
        subprocess.run([ruff, "format", str(path)], check=False, capture_output=True)
    except OSError:
        pass


def get_db_cli(app) -> type[Cli]:
    class DBCLI(Cli):
        def _get_router(self, name: str, validate: bool = True) -> Router | None:
            log = print if validate is True else (lambda *args, **kwargs: None)

            db = app.db.get(name)
            if db is None:
                log(f"Database '{name}' not found.")
                sys.exit(1)
                return

            if name == DB_QUEUE:
                dburi = app.config.QUEUE.get("database")
            elif name == DB_CACHE:
                dburi = app.config.CACHE.get("database")
            else:
                dburi = app.config.DATABASES.get(name, {}).get("database")

            if dburi == ":memory:":
                log(f"{name}: Cannot run migrations on in-memory database.")
                return

            if db.is_closed():
                db.connect()
            migrate_dir = Path("db", name)
            migrate_dir.mkdir(exist_ok=True)
            return Router(db, migrate_dir=migrate_dir)

        def prepare(self, db: str = "main"):
            """Bring the DB to a runnable state.

            Excecutes `db migrate` and `db seed` (if APP_ENV is no "test").

            Arguments:

            - db:
                Database name to prepare. Default is "main".

            """
            self.migrate(db=db)
            if app.env != "test":
                self.seed(db=db)

        def create(self, name: str = "auto", db: str = "main"):
            """Create a new migration file for all changes in the models.

            Arguments:

            - name:
                Optional name for the migration
            - db:
                Database name to create the migration for. Default is "main".

            """
            if DB_QUEUE == db:
                models = getattr(app.queue, "models", None)
            elif DB_CACHE == db:
                models = getattr(app.cache, "models", None)
            else:
                models = import_module(f"{app.name}.models")

            if not models:
                print("No models found.")
                sys.exit(0)

            router = self._get_router(db)
            assert router
            name = "_".join(name.lower().strip().split())
            migration = router.create(name, auto=models)
            if migration:
                print(f"{router.migrate_dir}/{migration}.py")

        def migrate(self, fake: bool = False, db: str = ""):
            """Run/emulate all the pending migrations.

            Arguments:

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
            for name in [*app.config.DATABASES.keys(), DB_QUEUE, DB_CACHE]:
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
                Target database name. Default is "main".

            """
            router = self._get_router(db)
            assert router
            router.rollback()

        def merge(self, name: str = "initial", db: str = "main"):
            """Merge all migrations into one.

            Arguments:

            - db:
                Target database name. Default is "main".

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

        def seed(self, name: str = "", db: str = "main"):
            """Run seed scripts for the given database.

            Seeds live under `db/seeds/` (or `db/seeds/<db>/` for non-default
            databases). They are registered as imports in the corresponding
            `__init__.py` and run in import order, honoring each seed's
            module-level `envs` tuple against the current `APP_ENV`.

            Arguments:

            - name:
                Optional seed name to run (without the `.py` suffix).
                If omitted, every registered seed runs in import order.
            - db:
                Target database name. Default is "main".

            """
            run_seeds(name=name, db=db)

    return DBCLI
