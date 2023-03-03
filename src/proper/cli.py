import os
import sys

from proper_cli import *  # noqa

from .cli_proper import ProperCli


def get_app():
    sys.path.append(str(os.getcwd()))
    try:
        from wsgi import app  # noqa
    except ImportError as err:
        print("---", err)
        return None
    return app


def run():
    app = get_app()
    if app is None:
        cli = ProperCli()
    else:
        cli = app.Cli()
    if cli:
        cli()
