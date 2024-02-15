import os

from proper import DEV, PROD, env


DATABASE_ENGINES = {
    "sqlite": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "db/sqlite.db",
    },
    "postgres": {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "[[ app_name ]]"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        # The connection is managed in a concern of the view,
        # and on the `on_teardown` and `on_error` hooks
        "autoconnect": False,
    },
    "maria": {
        "type": "peewee.MySQLDatabase",
        "database": os.getenv("DB_NAME", "[[ app_name ]]"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        # The connection is managed iin a concern of the view,
        # and on the `on_teardown` and `on_error` hooks
        "autoconnect": False
    },
}

if env == PROD:
    DATABASE: str = "postgres"
elif env == DEV:
    DATABASE: str = "sqlite"
else:
    DATABASE: str = "sqlite"
