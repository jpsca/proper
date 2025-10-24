import typing as t

from proper.errors import BadSecretKey
from proper.helpers import DotDict
from proper.units import DAYS, MB


default_config = {
    "DEBUG": False,
    "PROTOCOL": "http",
    "HOST": "localhost:2300",

    # List/tuple of secret keys, **oldest to newest**.
    # Every key in the list is valid, so you can periodically generate a new key
    # and remove the oldest one to add and extra layer of mitigation
    # against an attacker discovering a secret key.
    "SECRET_KEYS": (),

    # Turn off to let debugging middleware handle exceptions.
    "CATCH_ALL_ERRORS": True,

    # Limits the total content length (in bytes).
    # Raises a `RequestEntityTooLarge` exception if this value is exceeded.
    "MAX_CONTENT_LENGTH": 8 * MB,

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    "MAX_QUERY_SIZE": 1 * MB,

    "STATIC_URL": "/static/",
    "VIEWS_ASSETS_URL": "/static_v/",

    # The name of the header to use to `return a file
    # so the proxy or web-server does it instead of our application.
    # Lighttpd uses "X-Sendfile" while `NGINX uses "X-Accel-Redirect""",
    "STATIC_X_SENDFILE_HEADER": "",

    # Number of seconds before a non-used session key expires.
    "SESSION_LIFETIME": 30 * DAYS,
    "SESSION_COOKIE_NAME": "_session",
    "SESSION_COOKIE_DOMAIN": None,  # str | None
    "SESSION_COOKIE_PATH": "/",
    "SESSION_COOKIE_HTTPONLY": True,
    # Modern browsers place restriction on cookies without the "same-site" cookie attribute set.
    # To that end this attribute is set to `"Lax"` by default.
    "SESSION_COOKIE_SAMESITE": "Lax",  # Lax | Strict | None
}


def normalize_config(config: DotDict) -> DotDict:
    MIN_SECRET_LENGTH = 48
    for key in config.SECRET_KEYS:
        if len(key) < MIN_SECRET_LENGTH:
            raise BadSecretKey(
                f"Your secret_key, `{key}` used for verifying the "
                "integrity of signed cookies, is not secure enough. \n"
                f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                "and all random, no regular words or you'll be exposed to "
                "dictionary attacks."
            )

    if config.SESSION_COOKIE_SAMESITE not in ("Lax", "Strict", "None"):
        raise ValueError(
            "SESSION_COOKIE_SAMESITE must be one of: 'Lax', 'Strict', or 'None'."
        )

    config.DEBUG = bool(config.DEBUG)
    config.CATCH_ALL_ERRORS = bool(config.CATCH_ALL_ERRORS)
    config.SESSION_COOKIE_HTTPONLY = bool(config.SESSION_COOKIE_HTTPONLY)

    config.MAX_CONTENT_LENGTH = int(config.MAX_CONTENT_LENGTH)
    config.MAX_QUERY_SIZE = int(config.MAX_QUERY_SIZE)
    config.SESSION_LIFETIME = int(config.SESSION_LIFETIME)

    config.PROTOCOL = str(config.PROTOCOL)
    config.HOST = str(config.HOST)
    config.STATIC_URL = str(config.STATIC_URL)

    return config


def load_config(user_config: dict[str, t.Any] | type) -> DotDict:
    if isinstance(user_config, dict):
        config_data = user_config
    else:
        config_data = {
            key: getattr(user_config, key)
            for key in dir(user_config)
            if not key.startswith("_") and key.isupper()
        }

    config = DotDict(default_config)
    config.update(config_data)

    return normalize_config(config)
