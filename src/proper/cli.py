from proper_cli import *  # noqa

from .cli_app import get_app_cli
from .cli_proper import ProperCli


def run():
    app_cli = get_app_cli()
    if app_cli is None:
        cli = ProperCli()
    else:
        cli = app_cli()
    cli()
