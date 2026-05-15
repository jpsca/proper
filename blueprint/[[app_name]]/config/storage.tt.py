import os
import typing as t


env = os.getenv("APP_ENV", "dev")

DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
    # -- or --
    # "main": {
    #     "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
    #     "database": os.getenv("DB_NAME", "[[app_name]]"),
    #     "host": os.getenv("DB_HOST", "127.0.0.1"),
    #     "port": int(os.getenv("DB_PORT", 5432)),
    #     "user": os.getenv("DB_USER", "root"),
    #     "password": os.getenv("DB_PASSWORD", ""),
    #     # The connection is managed in a concern of the controllers,
    #     # and on the `on_teardown` and `on_error` hooks
    #     "autoconnect": False,
    # }
}


QUEUE = {
    "type": "huey.MemoryHuey",
    "immediate": True,
    "immediate_use_memory": True,
    # -- or --
    # "type": "huey.SqliteHuey",
    # "database": "storage/queue.sqlite3",
    # -- or --
    # "type": "huey.RedisHuey",
    # "name": "[[app_name]]",
}
QUEUE_CONSUMER = {
    # Number of workers to spawn.
    "workers": 1,
    # Enable periodic task scheduler?
    "periodic": True,
    # Default queue polling interval.
    "initial_delay": 0.1,
    # Exponential backoff factor when queue empty.
    "backoff": 1.15,
    # Maximum interval between polling events.
    "max_delay": 10.0,
    # Interval for the scheduler. Must be between 1 and 60s
    "scheduler_interval": 1,
    # Type of worker to use ("thread", "process", or "greenlet").
    "worker_type": "thread",
    # Whether to check worker health.
    "check_worker_health": True,
    # Interval for health checks.
    "health_check_interval": 10,
    # Whether to flush locks.
    "flush_locks": False,
    # Comma-separated extra locks to use.
    "extra_locks": "",
}

CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": ":memory:",
}


# --- Override config for testing ---
if env == "test":
    DATABASES["main"] = {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": ":memory:",
    }

    QUEUE = {
        "type": "huey.MemoryHuey",
        "immediate": True,
        "immediate_use_memory": True,
    }

    CACHE = {
        "type": "proper.cache.NoCache",
    }


# --- Override config for production ---
if env == "prod":
    DATABASES["main"] = {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "[[app_name]]"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        # The connection is managed in a concern of the controllers,
        # and on the `on_teardown` and `on_error` hooks
        "autoconnect": False,
    }

    QUEUE = {
        # Require redis package
        "type": "huey.RedisHuey",
        "name": "[[app_name]]",
    }

    CACHE = {
        "type": "proper.cache.SqliteCache",
        "database": "storage/cache.sqlite3",
    }
