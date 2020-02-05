from pathlib import Path
import os

from pyceo import option
import texteditor

from proper.support import secrets

from .core import core


__all__ = (
    "secret",
    "secrets_edit",
)


@core.command(help="Returns a secure secret_key")
@option("length")
def secret(length=secrets.SECRET_KEY_LEN):
    print(secrets.generate_secret_key(length))


@core.command(
    name="secrets:edit",
    help="""
Edit your encrypted secrets.

By default, the secrets from the current environment (as read from the
PROPER_ENV environment variable is used).

Alternatively, you can specify an environment (development, production,
texting, etc.)with the `env` option, or the full path of the encrypted
file, with the `path` option. The `path` option takes precedence.

""",
)
@option("path", help="Path of the encrypted file.")
@option("env", help="Edit secrets from this environment. Ignored if `path` is used.")
def secrets_edit(path=None, env=None):
    if path is None:
        if env is None:
            env = os.getenv("PROPER_ENV", "development")
        path = f"config/{env}/secrets.yaml.enc"

    path = Path(path)
    if not path.exists():
        raise SecretsNotFound(path)
    path.touch()
    content = secrets.read_secrets(path)
    if not content:
        spath = str(path)
        if env == "development" or "/development/" in spath:
            content = secrets.make_dev_default_secrets()
        elif env == "production" or "/production/" in spath:
            content = secrets.make_prod_default_secrets()
        else:
            content = secrets.make_default_secrets()

    print("You can edit your secrets now.")
    print("Do not forget to save your changes.")
    print("Waiting for you to close the editor...")

    new_content = texteditor.open(content, extension="yaml")
    secrets.save_secrets(path, new_content)

    print("Your secrets are safe.")


class SecretsNotFound(Exception):
    def __init__(self, path):
        message = (
            "\nI went looking for `" + str(path) + "` but it does not exists."
            + "\nYou must specify the path of your secrets file."
        )
        super().__init__(message)
