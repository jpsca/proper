import os
import typing as t
from pathlib import Path

from proper.errors import BadSecretKey
from proper.helpers import DAYS, HOURS, MB, logger


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"

DEV = "dev"
PROD = "prod"
TEST = "test"

MIN_SECRET_LENGTH = 48


class BaseConfig:
    def __contains__(self, name: t.Any) -> bool:
        return hasattr(self, name)

    def __getitem__(self, key: str) -> None:
        return getattr(self, key)

    def __setitem__(self, key: str, value: t.Any) -> None:
        setattr(self, key, value)

    def to_dict(self) -> dict[str, t.Any]:
        return {k: getattr(self, k) for k in dir(self) if not k.startswith("_")}

    def get(self, name: str, default: t.Any = None) -> t.Any:
        return getattr(self, name, default)

    def update(self, config: t.Any):
        if isinstance(config, dict):
            self.__dict__.update(config)
        else:
            self.__dict__.update(vars(config))


class Config(BaseConfig):
    DEBUG: bool = False
    PROTOCOL: str = "http"
    HOST: str = "localhost:2300"

    # List of secret keys, **oldest to newest**.
    # Every key in the list is valid, so you can periodically generate a new key
    # and remove the oldest one to add and extra layer of mitigation
    # against an attacker discovering a secret key.
    SECRET_KEYS: list[str] | tuple[str, ...]

    # Turn off to let debugging middleware handle exceptions.
    CATCH_ALL_ERRORS: bool = True

    # Limits the total content length (in bytes).
    # Raises a `RequestEntityTooLarge` exception if this value is exceeded.
    MAX_CONTENT_LENGTH: int = 8 * MB

    # Limits the content length (in bytes) of the query string.
    # Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.
    MAX_QUERY_SIZE: int = 1 * MB

    STATIC_URL: str = "/static/"
    VIEWS_ASSETS_URL: str = "/static/v/"

    # The name of the header to use to `return a file
    # so the proxy or web-server does it instead of our application.
    # Lighttpd uses "X-Sendfile" while `NGINX uses "X-Accel-Redirect""",
    STATIC_X_SENDFILE_HEADER: str = ""

    # Number of seconds before a non-used session key expires.
    SESSION_LIFETIME: int = 30 * DAYS
    SESSION_COOKIE_NAME: str = "_session"
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = False
    # Modern browsers place restriction on cookies without the "same-site" cookie attribute set.
    # To that end this attribute is set to `"Lax"` by default.
    SESSION_COOKIE_SAMESITE: t.Literal["Lax"] | t.Literal["Strict"] | None = "Lax"

    LOCALE_DEFAULT: str = "en"

    MAILER_DEFAULT_FROM: str = "hello@example.com"

    DATABASE: dict[str, t.Any] = {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
        "migrations": "db/migrations",
    }
    CACHE: dict[str, t.Any] = {
        "type": "proper.cache.SqliteCache",
        "database": ":memory:",
    }
    QUEUE: dict[str, t.Any] = {
        "type": "proper.queue.SqliteQueue",
        "database": ":memory:",
    }

    AUTH_HASH_NAME: str | None = None
    # `None` means using the default number for the hash".
    AUTH_ROUNDS: int | None = None
    AUTH_PASSWORD_MINLEN: int = 9
    AUTH_PASSWORD_MAXLEN: int = 1024
    # Number of seconds before a reset-password token expires.
    AUTH_TOKEN_LIFE: int = 3 * HOURS

    # Image content types that can be processed without being converted to
    # the fallback PNG format. If you want to use WebP or AVIF variants in
    # your application you can add image/webp or image/avif to this list.
    STORAGE_WEB_IMAGE_CONTENT_TYPES: list[str] | tuple[str, ...] = ("image/png", "image/jpeg", "image/gif")

    def validate(self):
        for key in self.SECRET_KEYS:
            if len(key) < MIN_SECRET_LENGTH:
                raise BadSecretKey(
                    f"Your secret_key, `{key}` used for verifying the "
                    "integrity of signed cookies, is not secure enough. \n"
                    f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                    "and all random, no regular words or you'll be exposed to "
                    "dictionary attacks."
                )


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
