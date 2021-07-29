"""Command Line User Interface for Proper itself.
"""
from pyceo import Cli

from .generators import gen_project
from .server import on_start


__all__ = ("ProperCli")


class ProperCli(Cli):
    __doc__ = """<b>Proper</b>

    This utility provides commands from Proper itself."""

    def welcome(self, host="0.0.0.0", port=5000):
        """Display the welcome message for the development server.

        Arguments:

        - host [0.0.0.0]
        - port [5000]

        """
        on_start(host=host, port=port)


def new(self, *args, **kwargs):
    gen_project(*args, **kwargs)


new.__doc__ = gen_project.__doc__
ProperCli.new = new


cli = ProperCli()
