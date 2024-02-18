import os
from datetime import timedelta
from pathlib import Path

from proper.helpers import DotDict, logger


__all__ = (
    "get_env",
    "env",
    "DEV",
    "PROD",
    "TEST",
)


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

    config.COMPONENTS_FOLDER = "components"
    config.COMPONENTS_URL = "/components/"

    config.SESSION_LIFETIME = timedelta(days=30).total_seconds()

    config.SESSION_COOKIE_NAME = "_session"
    config.SESSION_COOKIE_DOMAIN = None
    config.SESSION_COOKIE_PATH = "/"
    config.SESSION_COOKIE_HTTPONLY = True
    config.SESSION_COOKIE_SECURE = False
    config.SESSION_COOKIE_SAMESITE = None  # "Lax", "Strict", or None

    config.LOCALES_FOLDER = "locales"
    config.LOCALE_DEFAULT = "en"

    config.STATIC_FOLDER = "static"
    config.STATIC_URL = "/static/"
    # The name of the header to use to return a file
    # so the proxy or web-server does it instead of our application.
    # Lighttpd uses "X-Sendfile" while NGINX uses "X-Accel-Redirect"
    config.STATIC_X_SENDFILE_HEADER = ""

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
        logger.debug("%s var found: %s", ENV_VAR, env)
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        env = envfile.read_text().strip()
        logger.debug("%s file found: %s", ENV_VAR, env)
        return env

    logger.debug("Using default environment: %s", default)
    return default


env = get_env()
logger.debug("env is %s", env)
