# from pathlib import Path
# import os
# import sys
from pyceo import option

from ..server import display_running_message
from ..server import run_server

from .core import core, import_app


__all__ = ("run", )


@core.command(help="Run Proper’s development server.")
@option("host")
@option("port", type=int)
def run(host="0.0.0.0", port=3030):
    app = import_app()
    display_running_message(host, port)
    try:
        run_server(app, host, port)
    except KeyboardInterrupt:
        print("Goodbye!\n")
