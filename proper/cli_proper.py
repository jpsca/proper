"""Command Line User Interface for Proper itself.
"""
from proper_cli import Cli

from .generators import gen_project


class ProperCli(Cli):
    __doc__ = """<b>Proper</b>

    This utility provides commands from Proper itself."""

    def new(self, *args, **kwargs) -> None:
        gen_project(*args, **kwargs)


ProperCli.new.__doc__ = gen_project.__doc__
cli = ProperCli()
