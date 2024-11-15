import os
import typing as t
from pathlib import Path
from typing import Annotated

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
    SECRET_KEYS: Annotated[
        list[str] | tuple[str, ...],
        """List of secret keys, **oldest to newest**.
Every key in the list is valid, so you can periodically generate a new key
and remove the oldest one to add and extra layer of mitigation
against an attacker discovering a secret key""",
    ]
    CATCH_ALL_ERRORS: Annotated[
        bool, "Turn off to let debugging middleware handle exceptions.",
    ] = True

    MAX_CONTENT_LENGTH: Annotated[
        int,
        """Limits the total content length (in bytes).
Raises a `RequestEntityTooLarge` exception if this value is exceeded.""",
    ] = 8 * MB

    MAX_QUERY_SIZE: Annotated[
        int,
        """Limits the content length (in bytes) of the query string.
Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.""",
    ] = 1 * MB

    SESSION_LIFETIME: Annotated[
        int, """Number of seconds before a non-used session key expires.""",
    ] = 30 * DAYS
    SESSION_COOKIE_NAME: str = "_session"
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: Annotated[
        t.Literal["Lax"] | t.Literal["Strict"] | None,
        """Modern browsers place restriction on cookies without the "same-site" cookie attribute set.
To that end this attribute is set to `"Lax"` by default."""
    ] = "Lax"

    LOCALE_DEFAULT: str = "en"

    STATIC_URL: str = "/static/"
    VIEWS_ASSETS_URL: str = "/static/v/"

    STATIC_X_SENDFILE_HEADER: Annotated[
        str,
        """The name of the header to use to return a file
so the proxy or web-server does it instead of our application.
Lighttpd uses "X-Sendfile" while NGINX uses "X-Accel-Redirect""",
    ] = ""

    MAILER_DEFAULT_FROM: str = "hello@example.com"

    AUTH_HASH_NAME: str | None = None
    AUTH_ROUNDS: Annotated[
        int | None, "`None` means using the default number for the hash",
    ] = None
    AUTH_PASSWORD_MINLEN: int = 9
    AUTH_PASSWORD_MAXLEN: int = 1024
    AUTH_TOKEN_LIFE: Annotated[
        int, "Number of seconds before a reset-password token expires",
    ] = 3 * HOURS

    STORAGE_WEB_IMAGE_CONTENT_TYPES: Annotated[
        list[str] | tuple[str, ...],
        """Image content types that can be processed without being converted to
the fallback PNG format. If you want to use WebP or AVIF variants in
your application you can add image/webp or image/avif to this list.""",
    ] = ("image/png", "image/jpeg", "image/gif")

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

    STORAGE: dict[str, t.Any] | None = None

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
