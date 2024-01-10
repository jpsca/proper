from proper_cli import *  # noqa

from ._proper import ProperCL
from ._app import get_app_cli  # noqa


def run():
    ProperCL()()
