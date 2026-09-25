"""Benchmark app for Proper.

Three endpoints, modeled on the TechEmpower tests:

- `/plaintext`: static text. Measures the framework overhead alone.
- `/json`: serializes a small dict.
- `/fortunes`: reads 12 rows from SQLite and renders a Jx template.
  This is the one that resembles a real page.
"""
from pathlib import Path

from proper import App, current


HERE = Path(__file__).parent
DB_PATH = HERE / "fortunes.db"

config = {
    "SECRET_KEYS": ["*" * 50],
    "DEBUG": False,
    "DATABASES": {
        "main": {
            "type": "playhouse.sqlite_ext.SqliteExtDatabase",
            "database": str(DB_PATH),
            "pragmas": {"journal_mode": "wal", "cache_size": -64000},
        }
    },
}


def make_app() -> App:
    app = App(__name__, config)
    current.app = app

    from . import bench_controller  # noqa: F401  registers routes
    from .models import Fortune, seed

    Fortune._meta.database = app.db["main"]
    seed(app.db["main"])
    return app
