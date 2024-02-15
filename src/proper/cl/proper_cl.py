"""Command Line User Interface for Proper itself.
"""
from proper_cli import Cli

from proper.generators import gen_app


class ProperCL(Cli):
    __doc__ = """<fg=white;options=bold>Proper</> CLI

    This utility provides commands from Proper itself."""

    def new(self, path: str, *, name: str = "", force: bool = False) -> None:
        gen_app(path, name=name, force=force)


ProperCL.new.__doc__ = gen_app.__doc__
