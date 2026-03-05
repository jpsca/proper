import typing as t

from .errors import BadSecretKey, ConfigError
from .helpers import DotDict
from .units import DAYS, MB


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
    # Raises a `RequestEntityTooLarge` or an `UriTooLong` if this value is exceeded.
    "MAX_QUERY_SIZE": 1 * MB,

    # Limits the number of files, fields and the size of each part in a multipart form.
    "MAX_FORM_FILES": 10,
    "MAX_FORM_FIELDS": 100,
    "MAX_FORM_PART_SIZE": 2 * MB,

    "ASSETS_URL": "/assets/",

    # The name of the header to use to return a file
    # so the proxy or web-server does it instead of our application.
    # NGINX and Caddy uses "X-Accel-Redirect",
    # Apache and Lighttpd uses "X-Sendfile".
    # Leave empty to disable.
    "STATIC_X_SENDFILE_HEADER": "",

    # Number of seconds before a non-used session key expires.
    "SESSION_COOKIE_LIFETIME": 30 * DAYS,
    "SESSION_COOKIE_DOMAIN": None,  # str | None
    "SESSION_COOKIE_PATH": "/",
    "SESSION_COOKIE_HTTPONLY": True,
    # Modern browsers place restriction on cookies without the "same-site" cookie attribute set.
    # To that end this attribute is set to "Lax" by default.
    "SESSION_COOKIE_SAMESITE": "Lax",  # Lax | Strict | None

    "LOCALE_DEFAULT": "en",
    "TIMEZONE_DEFAULT": "UTC",
}


def normalize_config(config: DotDict) -> DotDict:
    MIN_SECRET_LENGTH = 48
    if not config.SECRET_KEYS:
        raise ConfigError(
            "SECRET_KEYS list is empty. Please provide at least one secret key."
        )

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
        raise ConfigError(
            "SESSION_COOKIE_SAMESITE must be one of: 'Lax', 'Strict', or 'None'."
        )

    config.DEBUG = bool(config.DEBUG)
    config.CATCH_ALL_ERRORS = bool(config.CATCH_ALL_ERRORS)
    config.SESSION_COOKIE_HTTPONLY = bool(config.SESSION_COOKIE_HTTPONLY)

    config.MAX_CONTENT_LENGTH = int(config.MAX_CONTENT_LENGTH)
    config.MAX_QUERY_SIZE = int(config.MAX_QUERY_SIZE)
    config.SESSION_COOKIE_LIFETIME = int(config.SESSION_COOKIE_LIFETIME)

    config.PROTOCOL = str(config.PROTOCOL)
    config.HOST = str(config.HOST)
    config.ASSETS_URL = str(config.ASSETS_URL)

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
