import typing as t
from pathlib import Path

import peewee as pw
from peewee_migrate.models import MIGRATE_TABLE
from peewee_migrate.router import Router

from ..constants import DB_CACHE, DB_QUEUE


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("pending_migrations",)


def pending_migrations(app: "App") -> dict[str, list[str]]:
    """The migrations in `db/<name>/` of each database that were not
    applied to it, `{name: [migration, ...]}`; the databases without any
    left out.

    It only reads: a database without the table of the applied migrations
    has none applied. A database in memory, or without a folder of
    migrations, is skipped.
    """
    pending: dict[str, list[str]] = {}
    for name in [*app.config.DATABASES.keys(), DB_QUEUE, DB_CACHE]:
        db = app.db.get(name)
        folder = Path("db", name)
        if db is None or db.database == ":memory:" or not folder.is_dir():
            continue
        files = sorted(f.stem for f in folder.iterdir() if Router.filemask.match(f.name))
        if not files:
            continue
        done = _applied(db)
        todo = [migration for migration in files if migration not in done]
        if todo:
            pending[name] = todo
    return pending


def _applied(db: pw.Database) -> set[str]:
    """The names of the migrations applied to `db`. A connection opened
    here is closed again."""
    was_closed = db.is_closed()
    try:
        if not db.table_exists(MIGRATE_TABLE):
            return set()
        return {row[0] for row in db.execute_sql(f"SELECT name FROM {MIGRATE_TABLE}")}
    finally:
        if was_closed:
            db.close()
