import logging
import os
from datetime import timedelta
from pathlib import Path

from proper.helpers import DotDict


__all__ = (
    "get_env",
    "env",
    "is_development_env",
    "is_testing_env",
    "is_staging_env",
    "is_production_env",
    "is_staging_or_production_env",
)

logger = logging.getLogger("proper")
logger.setLevel("DEBUG")


def get_default_config():
    config = DotDict()

    config.debug = False
    config.host = None

    # Used for verifying the integrity of signed cookies
    config.secret_keys = [""]

    # Turn off to let debugging middleware handle exceptions.
    config.catch_all_errors = True

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    config.max_content_length = 2**23  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    config.max_query_size = 2**20  # 1 MB

    config.session = DotDict()
    config.session.lifetime = timedelta(days=30).total_seconds()

    config.session.cookie = DotDict()
    config.session.cookie.name = "_session"
    config.session.cookie.domain = None
    config.session.cookie.path = "/"
    config.session.cookie.httponly = True
    config.session.cookie.secure = False
    config.session.cookie.samesite = None  # "Lax", "Strict", or None

    config.static = DotDict()
    config.static.host = None

    # When set to False then compressed files will not be created but static files
    # will still get md5 tagged.
    config.static.compress = True

    config.static.paths = [
        # Everything in the `static` folder is available at `/static/...`
        # You can add other paths/prefixes here
        # {"path": "FOLDER_PATH", "prefix": "URL"},
    ]

    config.mailer = DotDict()
    config.mailer.default_from = "hello@example.com"

    config.auth = DotDict()
    config.auth.hash_name = None  # default
    config.auth.rounds = None  # default
    config.auth.password_minlen = 9
    config.auth.password_maxlen = 1024
    config.auth.token_life = 10800  # 3 hours

    storage = config.storage = DotDict()

    # Image content types that can be processed without being converted to
    # the fallback PNG format. If you want to use WebP or AVIF variants in
    # your application you can add image/webp or image/avif to this list.
    storage.web_image_content_types = ["image/png", "image/jpeg", "image/gif"]

    return config


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"


def get_env(default="development"):
    env = os.getenv(ENV_VAR)
    if env:
        logger.debug(f"{ENV_VAR} var found: {env}")
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        env = envfile.read_text().strip()
        logger.debug(f"{ENV_VAR} file found: {env}")
        return env

    logger.debug("Using default environment")
    return default


env = get_env()
logger.debug(f"env is {env}")

is_development_env = is_dev_env = env == "development"
is_testing_env = env == "testing"
is_staging_env = env == "staging"
is_production_env = is_prod_env = env == "production"
is_staging_or_production_env = is_staging_env or is_production_env
