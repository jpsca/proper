from pathlib import Path
import os

from pyceo import option
from proper_config import secrets

from proper.support.secrets import (
    SECRET_KEY_LEN,
    generate_secret_key,
    make_default_secrets,
    make_dev_default_secrets,
    make_prod_default_secrets,
)

from .core import core


__all__ = (
    "secret",
    "secrets_edit",
)


@core.command(help="Returns a secure secret_key")
@option("length")
def secret(length=SECRET_KEY_LEN):
    print(generate_secret_key(length))


@core.command(name="secrets:edit")
@option("path", help="Path of the encrypted file.")
@option("env", help="Edit secrets from this environment. Ignored if `path` is used.")
def secrets_edit(path=None, env=None):
    """Edit your encrypted secrets.

    By default, the secrets from the current environment (as read from the
    PROPER_ENV environment variable is used).

    Alternatively, you can specify an environment (development, production,
    texting, etc.) with the `env` option, or the full path of the encrypted
    file, with the `path` option. The `path` option takes precedence.

    """
    if path is None:
        if env is None:
            env = os.getenv("PROPER_ENV", "development")
        path = f"config/{env}/secrets.yaml.enc"

    spath = str(path)
    if env == "development" or "/development/" in spath:
        default = make_dev_default_secrets()
    elif env == "production" or "/production/" in spath:
        default = make_prod_default_secrets(MIN_SECRET_LENGTH)
    else:
        default = make_default_secrets()

    secrets.edit_secrets(path, default)
