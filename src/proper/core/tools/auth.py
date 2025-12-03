from proper.errors import ConfigError
from proper.helpers import get_class
from proper.units import HOURS


DEFAULT_CONFIG = {
    "AUTH_CLASS": "proper.auth.Auth",
    # The name of the hashing algorithm to use
    "AUTH_HASH_NAME": None,  # str | None
    #`None` means using the default number for the hash".
    "AUTH_ROUNDS": None,  # int | None
    "AUTH_PASSWORD_MINLEN": 9,
    "AUTH_PASSWORD_MAXLEN": 1024,
    # Number of seconds before a reset-password token expires.
    "AUTH_TOKEN_LIFE": 3 * HOURS,
}


def setup(app):
    for name, value in DEFAULT_CONFIG.items():
        app.config.setdefault(name, value)
    validate_config(app.config)

    Auth = get_class(app.config.AUTH_CLASS)
    app.auth = Auth(
        secret_keys=app.config.SECRET_KEYS,
        hash_name=app.config.AUTH_HASH_NAME,
        rounds=app.config.AUTH_ROUNDS,
        password_minlen=app.config.AUTH_PASSWORD_MINLEN,
        password_maxlen=app.config.AUTH_PASSWORD_MAXLEN,
    )


def validate_config(config):
    if not isinstance(config.AUTH_CLASS, (str, type)):
        raise ConfigError("'AUTH_CLASS' must be a string or a class")

    if config.AUTH_HASH_NAME is not None and not isinstance(config.AUTH_HASH_NAME, str):
        raise ConfigError("'AUTH_HASH_NAME' must be a string or None")

    if (
        config.AUTH_ROUNDS is not None
        and (not isinstance(config.AUTH_ROUNDS, int) or config.AUTH_ROUNDS < 1)
    ):
        raise ConfigError("'AUTH_ROUNDS' must be a positive integer or None")

    if not isinstance(config.AUTH_PASSWORD_MINLEN, int) or config.AUTH_PASSWORD_MINLEN < 1:
        raise ConfigError("'AUTH_PASSWORD_MINLEN' must be a positive integer")

    if not isinstance(config.AUTH_PASSWORD_MAXLEN, int) or config.AUTH_PASSWORD_MAXLEN < 1:
        raise ConfigError("'AUTH_PASSWORD_MAXLEN' must be a positive integer")

    if not isinstance(config.AUTH_TOKEN_LIFE, int) or config.AUTH_TOKEN_LIFE < 1:
        raise ConfigError("'AUTH_TOKEN_LIFE' must be a positive integer")
