"""Command Line User Interface for Proper itself.
"""
from properconf.secrets import generate_token
from pyceo import Cli

from proper.constants import MIN_SECRET_LENGTH
from proper.server import on_start
from proper.version import __version__

from .setup import *  # noqa


class ProperCli(Cli, SetupMixin):
    __doc__ = f"""<b>Proper v{__version__}</b>

    This utility provides commands from Proper itself."""

    def welcome(self, host="0.0.0.0", port=5000):
        """Display the welcome message for the development server.

        Arguments:

        - host [0.0.0.0]
        - port [5000]

        """
        on_start(host=host, port=port)

    def secret(self, length=MIN_SECRET_LENGTH):
        """Returns a secure secret_key.

        Arguments:

        - length [DEFAULT]

        """
        print(generate_token())


cli = ProperCli()
