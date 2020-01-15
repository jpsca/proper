"""
## proper.support.secrets

"""
import os
import string
from pathlib import Path
from textwrap import dedent

from cryptography.fernet import Fernet

from ..constants import MIN_SECRET_LENGTH


__all__ = (
    "MASTER_KEY_FILE",
    "MASTER_KEY_ENV",
    "generate_master_key",
    "new_master_key_file",
    "make_default_secrets",
    "make_dev_default_secrets",
    "make_prod_default_secrets",
    "read_secrets",
    "save_secrets",
    "read_master_key",
)


MASTER_KEY_FILE = "master.key"
MASTER_KEY_ENV = "PROPER_MASTER_KEY"

CHARS = string.ascii_letters + string.digits + "&*"
CHARS_LEN = 64
SECRET_KEY_LEN = 64


def generate_secret_key(key_len=SECRET_KEY_LEN):
    return "".join([CHARS[ord(os.urandom(1)) % CHARS_LEN] for i in range(key_len)])


def generate_master_key():
    return Fernet.generate_key()


def new_master_key_file(parent_path):
    master_key = generate_master_key()
    (Path(parent_path) / MASTER_KEY_FILE).write_bytes(master_key)
    return master_key


def make_default_secrets():
    return dedent(
        f"""\
    # This is an encrypted YAML file.
    #
    # Your can safely store here credentials like API keys and such,
    # and commit this file to your source version control system.
    # -------------------------------------------------------------

    # foo: "bar"
    """
    )


def make_dev_default_secrets():
    return dedent(
        f"""\
    # This is an encrypted YAML file for development.
    #
    # Your can safely store here credentials used in development,
    # like API keys and such, and commit this file to your source
    # version control system.
    # -------------------------------------------------------------

    # foo: "bar"
    """
    )


def make_prod_default_secrets():
    return dedent(
        f"""\
    # This is an encrypted YAML file for production.
    #
    # Your can safely store here credentials used in production,
    # like API keys and such, and commit this file to your source
    # version control system.
    # -------------------------------------------------------------

    # Your secret key is used for verifying the integrity of signed cookies.
    # If you change this key, all old signed cookies will become invalid
    # Make sure the secret is at least {MIN_SECRET_LENGTH} characters and
    # all random, no regular words or you'll be exposed to dictionary attacks.
    # You can use `proper secret` to generate a secure secret key.
    secret_key: "{generate_secret_key()}"
    """
    )


def read_master_key(parent_path, error_if_not_found=True):
    master_key = os.getenv(MASTER_KEY_ENV, "").strip().encode("utf8")
    if not master_key:
        key_path = Path(parent_path) / MASTER_KEY_FILE
        if key_path.is_file():
            master_key = key_path.read_bytes().strip()

    if error_if_not_found and not master_key:
        raise IOError(
            f"Master key not found. Either load a `{MASTER_KEY_FILE}` beside your "
            f"secrets file, or set and environment variable `{MASTER_KEY_ENV}` "
            "with the master key value (the environment variable takes precendence "
            "over the file)."
        )
    return master_key


def read_secrets(secrets_path, *, master_key=None):
    """Takes a path to an encrypted secrets file and returns its contents.
    decrypted.


    Arguments are:

        secrets_path (str):
            The path to an encripted secrets file. It's assumed that the master key
            is in the same folder or in an environment variable.

    Returns (str):

        The unencrypted secrets content.

    """
    secrets_path = Path(secrets_path)
    enc_content = secrets_path.read_bytes()
    if not enc_content:
        return ""
    master_key = master_key or read_master_key(secrets_path.parent)
    content = Fernet(master_key).decrypt(enc_content)
    return content.decode("utf8")


def save_secrets(secrets_path, content, *, master_key=None):
    """Takes a string, encrypts it using a `master.key` that
    should be in the same folder, saves it at `secrets_path`, and returns the
    unencrypted config.

    Arguments are:

        secrets_path (str):
            The path to an encripted secrets file. It's assumed that the master key
            is in the same folder or in an environment variable.

        content (str):
            The new content of the secrets file to be encrypted

        master_key (bytes):
            Optional. Use this as master_key, instead of trying to read it from a
            file or an environment variable.

    Returns (dict):

        The unencrypted and parsed-into-a-dict secrets.

    """
    secrets_path = Path(secrets_path)
    master_key = master_key or read_master_key(secrets_path.parent)
    enc_content = Fernet(master_key).encrypt(content.encode("utf8"))
    secrets_path.write_bytes(enc_content)
