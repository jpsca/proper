import importlib
import os
import sys
from pathlib import Path

from proper_cli import *  # noqa

from ._app import get_app_cli  # noqa
from ._proper import ProperCL


def run():
    from proper import App

    cwd = Path(os.getcwd())
    wsgi_py = cwd / "wsgi.py"
    if wsgi_py.is_file():
        if cwd not in sys.path:
            sys.path.append(str(cwd))
        module = importlib.import_module("wsgi")
        if hasattr(module, "app") and isinstance(module.app, App):
            appCL = get_app_cli(module.app)
            return appCL()()

    return ProperCL()()
