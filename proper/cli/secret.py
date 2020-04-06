from pyceo import option

from proper.support import secrets
from proper.constants import MIN_SECRET_LENGTH

from .core import core


__all__ = ("secret",)


@core.command(help="Returns a secure secret_key")
@option("length")
def secret(length=MIN_SECRET_LENGTH):
    print(secrets.generate_secret_key(length))
