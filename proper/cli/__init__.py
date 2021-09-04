"""Command Line User Interface for Proper itself.
"""
from pyceo import Cli

from proper.generators import gen_project
from .welcome import welcome_message


__all__ = ("ProperCli")


class ProperCli(Cli):
    __doc__ = """<b>Proper</b>

    This utility provides commands from Proper itself."""


def new(self, *args, **kwargs):
    gen_project(*args, **kwargs)


def welcome(self, *args, **kwargs):
    welcome_message(*args, **kwargs)


ProperCli.new = new
ProperCli.new.__doc__ = gen_project.__doc__

ProperCli.welcome = welcome
ProperCli.welcome.__doc__ = welcome_message.__doc__


cli = ProperCli()
