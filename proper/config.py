from datetime import timedelta

from proper_config import ConfigDict


__all__ = ("get_default_config", )

default_config = {
    "debug": False,

    # Turn off to let debugging middleware handle exceptions.
    "catch_all_errors": True,

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    "max_content_length": 2 ** 23,  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    "max_query_size": 2 ** 20,  # 1 MB

    # Session config
    "session": {
        "cookie_name": "_session",
        "cookie_domain": None,
        "cookie_path": "/",
        "cookie_httponly": True,
        "cookie_secure": False,
        "cookie_samesite": None,
        "lifetime": timedelta(days=30).total_seconds(),
    },

    # Static assets
    "static": {
        "host": None,

        # When set to False then compressed files will not be created but static files
        # will still get md5 tagged.
        "compress": True,

        "paths": [
            {"path": "static/public", "prefix": "static/"}
        ]
    },

    "database_dialect": "sqlite+pysqlite",
    "database_name": ":memory:",
    "database_host": None,
    "database_port": None,
    "database_user": None,
    "database_password": None,
    "database_engine_options": None,
    "database_session_options": {"expire_on_commit": False},
    "alembic_migrations": None,

    "auth_hash_name": None,
    "auth_rounds": None,
    "auth_password_minlen": 9,
    "auth_password_maxlen": 1024,
    "auth_token_life": 10800,  # 3 hours
}


def get_default_config():
    return ConfigDict(default_config)
