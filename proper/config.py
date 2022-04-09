import logging
import os
from datetime import timedelta
from pathlib import Path

from proper.helpers import Dot


__all__ = (
    "get_env",
    "env",
    "is_development_env",
    "is_testing_env",
    "is_staging_env",
    "is_production_env",
    "is_staging_or_production_env",
)

logger = logging.getLogger(__name__)


def get_default_config():
    config = Dot()

    config.debug = False
    config.host = None

    # Used for verifying the integrity of signed cookies
    config.secret_key = ""

    # Turn off to let debugging middleware handle exceptions.
    config.catch_all_errors = True

    # Limits the total content length (in bytes).
    # Raises a RequestEntityTooLarge exception if this value is exceeded.
    config.max_content_length = 2**23  # 8 MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    config.max_query_size = 2**20  # 1 MB

    config.session = Dot()
    config.session.lifetime = timedelta(days=30).total_seconds()

    config.session.cookie = Dot()
    config.session.cookie.name = "_session"
    config.session.cookie.domain = None
    config.session.cookie.path = "/"
    config.session.cookie.httponly = True
    config.session.cookie.secure = False
    config.session.cookie.samesite = None  # "Lax", "Strict", or None

    config.static = Dot()
    config.static.host = None

    # When set to False then compressed files will not be created but static files
    # will still get md5 tagged.
    config.static.compress = True

    config.static.paths = [
        # Everything in the `static` folder is available at `/static/...`
        # You can add other paths/prefixes here
        # {"path": "FOLDER_PATH", "prefix": "URL"},
    ]

    config.database = Dot()
    config.database.dialect = "sqlite+pysqlite"
    config.database.name = ":memory:"
    config.database.host = None
    config.database.port = None
    config.database.user = None
    config.database.password = None
    config.database.engine_options = None  # default
    config.database.session_options = {"expire_on_commit": False}
    config.database.migrations = None

    config.mailer = Dot()
    config.mailer.default_from = "hello@example.com"

    scheduler = config.scheduler = Dot()
    scheduler.type = "redis"
    # If True, run synchronously and ignore the type above
    scheduler.immediate = True

    scheduler.results = True  # Store return values of tasks
    scheduler.store_none = False  # If a task returns None, do not save to results
    scheduler.utc = True  # Use UTC for all times internally
    scheduler.blocking = True  # Perform blocking pop rather than poll Redis

    scheduler.connection = Dot()
    scheduler.connection.host = "localhost"
    scheduler.connection.port = 6379
    scheduler.connection.db = 0
    scheduler.connection.connection_pool = None  # Definitely you should use pooling
    scheduler.connection.read_timeout = 1  # If not polling (blocking pop), use timeout
    scheduler.connection.url = None  # Allow Redis config via a DSN

    scheduler.consumer = Dot()
    scheduler.consumer.workers = 1
    scheduler.consumer.worker_type = "thread"
    scheduler.consumer.initial_delay = 0.1  # Smallest polling interval
    scheduler.consumer.backoff = 1.15  # Exponential backoff using this rate
    scheduler.consumer.max_delay = 10.0  # Max possible polling interval
    scheduler.consumer.scheduler_interval = 1  # Check schedule every second
    scheduler.consumer.periodic = True  # Enable crontab feature
    scheduler.consumer.check_worker_health = True  # Enable worker health checks
    scheduler.consumer.health_check_interval = 1  # Check worker health every second

    config.auth = Dot()
    config.auth.hash_name = None  # default
    config.auth.rounds = None  # default
    config.auth.password_minlen = 9
    config.auth.password_maxlen = 1024
    config.auth.token_life = 10800  # 3 hours

    config.storage = Dot()

    return config


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"


def get_env(default="development"):
    env = os.getenv(ENV_VAR)
    if env:
        logger.debug("%s var found: %s", ENV_VAR, env)
        return env
    envfile = Path(ENV_FILE)
    if envfile.exists():
        env = envfile.read_text().strip()
        logger.debug("%s file found: %s", ENV_VAR, env)
        return env

    logger.debug("Using default environment")
    return default


env = get_env()
logger.debug("env is %{env}s", env=env)

is_development_env = is_dev_env = env == "development"
is_testing_env = env == "testing"
is_staging_env = env == "staging"
is_production_env = is_prod_env = env == "production"
is_staging_or_production_env = is_staging_env or is_production_env
