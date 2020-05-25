from textwrap import dedent
import os
import string


__all__ = (
    "generate_secret_key",
    "make_default_secrets",
    "make_dev_default_secrets",
    "make_prod_default_secrets",
)

CHARS = string.ascii_letters + string.digits + "&*"
CHARS_LEN = 64
SECRET_KEY_LEN = 64


def generate_secret_key(key_len=SECRET_KEY_LEN):
    return "".join([CHARS[ord(os.urandom(1)) % CHARS_LEN] for i in range(key_len)])


def make_default_secrets():
    return dedent(
        """\
    # This is an encrypted YAML file.
    #
    # Your can safely store here credentials like API keys and such,
    # and commit this file to your source version control system.
    # -------------------------------------------------------------

    # foo: "bar"
    """)


def make_dev_default_secrets():
    return dedent(
        """\
    # This is an encrypted YAML file for development.
    #
    # Your can safely store here credentials used in development,
    # like API keys and such, and commit this file to your source
    # version control system.
    # -------------------------------------------------------------

    # foo: "bar"
    """)


def make_prod_default_secrets(min_secret_length):
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
    # Make sure the secret is at least {min_secret_length} characters and
    # all random, no regular words or you'll be exposed to dictionary attacks.
    # You can use `proper secret` to generate a secure secret key.
    secret_key: "{generate_secret_key()}"
    """)
