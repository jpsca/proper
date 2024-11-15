import os

from proper import PROD, TEST, Config, env


config = Config()

config.DATABASE = {
    "type": "playhouse.sqlite_ext.SqliteExtDatabase",
    "database": "storage/app.sqlite3",
    "migrations": "db/migrations",
}

config.CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": ":memory:",
}

config.QUEUE = {
    "type": "proper.queue.SqliteQueue",
    "database": ":memory:",
}


# --- Override config for testing ---
if env == TEST:
    config.QUEUE = {
        "type": "proper.queue.NoQueue",
    }


# --- Override config for production ---
if env == PROD:
    config.DATABASE = {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "dbname"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        # The connection is managed in a concern of the controllers,
        # and on the `on_teardown` and `on_error` hooks
        "autoconnect": False,
    }

    config.CACHE = {
        "type": "proper.cache.SqliteCache",
        "database": "storage/app_cache.sqlite3",
    }

    config.QUEUE = {
        "type": "proper.queue.PostgresQueue",
        "database": os.getenv("DB_NAME", "dbname"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }