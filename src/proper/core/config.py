import inspect
import os
import typing as t
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from proper.errors import BadSecretKey, ConfigError
from proper.helpers import DAYS, HOURS, MB, logger


ENV_VAR = "APP_ENV"
ENV_FILE = ".APP_ENV"

DEV = "dev"
PROD = "prod"
TEST = "test"

MIN_SECRET_LENGTH = 48


class ConfigSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    DEBUG: bool = False
    PROTOCOL: str = "http"
    HOST: str = "localhost:2300"
    SECRET_KEYS: list[str] | tuple[str, ...] = Field(
        description="""List of secret keys, **oldest to newest**.
Every key in the list is valid, so you can periodically generate a new key
and remove the oldest one to add and extra layer of mitigation
against an attacker discovering a secret key""",
    )
    CATCH_ALL_ERRORS: bool = Field(
        description="Turn off to let debugging middleware handle exceptions.",
        default=True,
    )
    MAX_CONTENT_LENGTH: int = Field(
        description="""Limits the total content length (in bytes).
Raises a `RequestEntityTooLarge` exception if this value is exceeded.""",
        default=8 * MB
    )
    MAX_QUERY_SIZE: int = Field(
        description="""Limits the content length (in bytes) of the query string.
Raises a RequestEntityTooLarge or an UriTooLong if this value is exceeded.""",
        default=1 * MB
    )

    SESSION_LIFETIME: int = Field(
        description="""Number of seconds before a non-used session key expires.""",
        default=30 * DAYS,
    )
    SESSION_COOKIE_NAME: str = "_session"
    SESSION_COOKIE_DOMAIN: str | None = None
    SESSION_COOKIE_PATH: str = "/"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: t.Literal["Lax"] | t.Literal["Strict"] | None = None

    LOCALE_DEFAULT: str = "en"

    STATIC_URL: str = "/static/"
    VIEWS_ASSETS_URL: str = "/static/v/"

    STATIC_X_SENDFILE_HEADER: str = Field(
        description="""The name of the header to use to return a file
so the proxy or web-server does it instead of our application.
Lighttpd uses "X-Sendfile" while NGINX uses "X-Accel-Redirect""",
        default="",
    )

    MAILER_DEFAULT_FROM: str = "hello@example.com"

    AUTH_HASH_NAME: str | None = None
    AUTH_ROUNDS: int | None = Field(description="`None` means using the default number for the hash", default=None)
    AUTH_PASSWORD_MINLEN: int = 9
    AUTH_PASSWORD_MAXLEN: int = 1024
    AUTH_TOKEN_LIFE: int = Field(
        description="Nmber of seconds before a reset-password token expires",
        default=3 * HOURS,
    )

    STORAGE_WEB_IMAGE_CONTENT_TYPES: list[str] | tuple[str, ...] = Field(
        description="""Image content types that can be processed without being converted to
the fallback PNG format. If you want to use WebP or AVIF variants in
your application you can add image/webp or image/avif to this list.""",
        default=("image/png", "image/jpeg", "image/gif"),
    )

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

    @field_validator("SECRET_KEYS")
    @classmethod
    def validate_secret_keys(
        cls, value: list[str] | tuple[str, ...]
    ) -> list[str] | tuple[str, ...]:
        secret_keys = value or [""]
        for key in secret_keys:
            if len(key) < MIN_SECRET_LENGTH:
                raise BadSecretKey(
                    f"Your secret_key, `{key}` used for verifying the "
                    "integrity of signed cookies, is not secure enough. \n"
                    f"Make sure is at least {MIN_SECRET_LENGTH} characters "
                    "and all random, no regular words or you'll be exposed to "
                    "dictionary attacks."
                )
        return value


def validate_config(dict_or_module: t.Any) -> dict[str, t.Any]:
    if isinstance(dict_or_module, dict):
        data = dict_or_module
    else:
        data = {
            name: value for name, value in vars(dict_or_module).items()
            if not (name.startswith("_") or inspect.ismodule(value))
        }
    try:
        m = ConfigSchema(**data)
    except ValidationError as e:
        raise ConfigError() from e

    config_dict = m.model_dump()
    config_dict.update(m.__pydantic_extra__ or {})
    return config_dict


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
