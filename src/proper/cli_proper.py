"""Command Line User Interface for Proper itself.
"""
from proper_cli import Cli

from .generators import gen_project


class ProperCli(Cli):
    __doc__ = """<fg=white;options=bold>Proper</> CLI

    This utility provides commands from Proper itself."""

    def new(self, path: str, *, name: str = "", force: bool = False) -> None:
        gen_project(path, name=name, force=force)


ProperCli.new.__doc__ = gen_project.__doc__
