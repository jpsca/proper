import typing as t
from datetime import timedelta

from .database import config as database_config
from .scheduler import config as scheduler_config
from .storage import config as storage_config


config = {
    "debug": False,
    "host": "http://127.0.0.1:2300",

    "middleware": [
        "proper.pipeline.head_to_get",
        "proper.pipeline.method_override",
    ],

    # If one of these functions does `response.stop = True`,
    # the rest is skipped.
    "middleware_groups": {
        "web": [
            "proper.pipeline.fetch_session",
            "proper.pipeline.dispatch",
            "proper.pipeline.put_session",
            "proper.pipeline.strip_body_if_head",
        ],
    },
    "default_middleware_group": "web",

    # List of secret keys, **oldest to newest**.
    # Used for verifying the integrity of signed cookies, signed URLs, etc.
    # Every key in the list is valid, so you can periodically generate a new key
    # and remove the oldest one to add and extra layer of mitigation
    # against an attacker discovering a secret key
    "secret_keys": [],

    # Turn off to let debugging middleware handle exceptions.
    "catch_all_errors": True,

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    "max_content_length": 2**23,  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    "max_query_size": 2**20,  # 1 MB

    "session": {
        "lifetime": timedelta(days=30).total_seconds(),
        "cookie": {
            "name": "_session",
            "domain": None,
            "path": "/",
            "httponly": True,
            "secure": False,
            # "Lax", "Strict", or None
            "samesite": None,
        },
    },

    "static": {
        "host": None,

        # When set to False then compressed files will not be created but static files
        # will still get md5 tagged.
        "compress": True,

        # Everything in the `static` folder is available at `/static/...`
        # You can add other paths/prefixes here
        "paths": [
            # {"path": "FOLDER_PATH", "prefix": "URL"},
        ],
    },

    "mailer": {
        "default_from": "hello@example.com",
    },

    "database": database_config,
    "scheduler": scheduler_config,
    "storage": storage_config,
}
