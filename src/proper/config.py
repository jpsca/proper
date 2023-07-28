import logging
import os
from datetime import timedelta
from pathlib import Path

from proper.helpers import DotDict


__all__ = (
    "get_env",
    "env",
    "DEV",
    "PROD",
    "TEST",
)

logger = logging.getLogger("proper")
logger.setLevel("DEBUG")


def get_default_config():
    config = DotDict()

    config.DEBUG = False
    config.HOST = None

    # List of secret keys, **oldest to newest**.
    # Every key in the list is valid, so you can periodically generate a new key
    # and remove the oldest one to add and extra layer of mitigation
    # against an attacker discovering a secret key
    config.SECRET_KEYS = [""]

    # Turn off to let debugging middleware handle exceptions.
    config.CATCH_ALL_ERRORS = True

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    config.MAX_CONTENT_LENGTH = 2**23  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    config.MAX_QUERY_SIZE = 2**20  # 1 MB

    config.SESSION_LIFETIME = timedelta(days=30).total_seconds()

    config.SESSION_COOKIE_NAME = "_session"
    config.SESSION_COOKIE_DOMAIN = None
    config.SESSION_COOKIE_PATH = "/"
    config.SESSION_COOKIE_HTTPONLY = True
    config.SESSION_COOKIE_SECURE = False
    config.SESSION_COOKIE_SAMESITE = None  # "Lax", "Strict", or None

    config.STATIC_HOST = None

    # When set to False then compressed files will not be created but static files
    # will still get md5 tagged.
    config.STATIC_COMPRESS = True

    config.STATIC_PATHS = [
        # Everything in the `static` folder is available at `/static/...`
        # You can add other paths/prefixes here
        # {"path": "FOLDER_PATH", "prefix": "URL"},
    ]

    config.MAILER_DEFAULT_FROM = "hello@example.com"

    config.AUTH_HASH_NAME = None  # default
    config.AUTH_ROUNDS = None  # default
    config.AUTH_PASSWORD_MINLEN = 9
    config.AUTH_PASSWORD_MAXLEN = 1024
    config.AUTH_TOKEN_LIFE = 10800  # 3 hours

    # Image content types that can be processed without being converted to
    # the fallback PNG format. If you want to use WebP or AVIF variants in
    # your application you can add image/webp or image/avif to this list.
    config.STORAGE_WEB_IMAGE_CONTENT_TYPES = ["image/png", "image/jpeg", "image/gif"]

    return config


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"

DEV = "dev"
PROD = "prod"
TEST = "test"


def get_env(default=DEV):
    env = os.getenv(ENV_VAR)
    if env:
        logger.debug(f"{ENV_VAR} var found: {env}")
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        env = envfile.read_text().strip()
        logger.debug(f"{ENV_VAR} file found: {env}")
        return env

    logger.debug(f"Using default environment: {default}")
    return default


env = get_env()
logger.debug(f"env is {env}")
