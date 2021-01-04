from pyceo import Cli

from .generators import GeneratorsCli


class ApplicationCli(Cli):
    g = GeneratorsCli
