"""
Default configuration values and validation logic for user-provided config.

For tool-specific configuration (db, auth, etc.), see the `tools/` folder.
"""
import typing as t

from ..errors import BadSecretKey, ConfigError
from ..helpers import DotDict
from ..units import DAYS, MB


default_config = {
    "DEBUG": False,
    "PROTOCOL": "http",
    "PORT": 2300,
    "HOST": "localhost:2300",

    # Where the server finds the app, as "package.module:variable". Empty
    # means the `app` variable of the module that created it.
    "APP_TARGET": "",

    # How many server workers `proper run` starts in each process: threads
    # sharing the process and its memory.
    "WORKERS": 1,

    # How many copies of the web server `proper run` starts, all on the same
    # port. One is right for most machines. On free-threaded Python the
    # threads of one process contend for its shared objects, so with four
    # or more cores a second process adds throughput (about 10% at 16
    # threads) for another copy of the app in memory.
    "PROCESSES": 1,

    # Proper serves on free-threaded Python (a "3.14t" build), and `proper
    # run` refuses to start otherwise. Set to True to serve with the GIL
    # anyway, at the cost of memory and parallelism.
    "ALLOW_GIL": False,

    # Restart the server when the code changes. `None` follows `DEBUG`.
    "RELOAD": None,
    # Where the views are compiled to, as Python modules (by minijx).
    # Relative to the app's parent folder. See `proper.compile`.
    "COMPILED_PATH": "_compiled",

    # Custom block tags for the views, `{"name": function}`:
    # `{% name args %}body{% endname %}` calls `function(args, caller=...,
    # template=...)`, where `caller()` renders the body. `cache` is Proper's.
    "TEMPLATE_TAGS": {},

    # List/tuple of secret keys, **oldest to newest**. New values are signed
    # with the newest one and every key in the list is accepted, so you can
    # rotate: append a new key, and once everything signed with the oldest
    # has expired, remove it. This mitigates an attacker discovering a key.
    "SECRET_KEYS": (),

    # Turn off to let something else, outside the application,
    # like a proxy or web-server, handle the unhandled exceptions.
    "CATCH_ALL_ERRORS": True,

    # How many threads run your code. Each request occupies one for its
    # whole duration, so this is how many requests the app can work on at
    # once - and, since every thread opens its own database connection,
    # how many connections it can hold. It is a total for the whole
    # process, split between its `WORKERS`. `0` uses Python's default of
    # `min(32, cpu_count + 4)`.
    "MAX_THREADS": 0,

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

    "CABLE_PATH": "/cable",

    # Port where the cable (`Cable`) serves the WebSockets of the
    # channels, from the process `proper run` starts. In production a proxy
    # routes `CABLE_PATH` here; in `DEBUG` the browser connects to this port
    # directly.
    "CABLE_PORT": 0,

    # Browser origins allowed to open a WebSocket besides the app's own
    # (`HOST`, or the `Host` the browser connected to), such as
    # `["https://app.example.com"]`. Other sites' pages are refused.
    "CABLE_ALLOWED_ORIGINS": [],

    # Seconds between the pings the server sends on every WebSocket, so
    # clients can tell a dead connection from a quiet one. `0` sends none.
    "CABLE_PING_INTERVAL": 3,

    # A connection with more than `CABLE_MAX_PENDING_BYTES` queued that got
    # nothing through in `CABLE_STALL_TIMEOUT` seconds is a client that is
    # not reading, and the server closes it. So is one with ten times as
    # many, at any speed. Keep ten times it below the cable's
    # `max_outbound_queue_bytes` (64 MB), where wse starts dropping
    # broadcasts instead. `0` is no limit.
    "CABLE_MAX_PENDING_BYTES": 4 * 1024 * 1024,
    "CABLE_STALL_TIMEOUT": 10,

    "IMPORT_MAP": {
        "@hotwired/stimulus": "js/vendor/stimulus.js",
        "@hotwired/turbo": "js/vendor/turbo.js",
    },
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

    config.MAX_THREADS = int(config.MAX_THREADS)

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
