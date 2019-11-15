from pathlib import Path
import os
import sys

from pyceo import Manager

from proper.version import __version__


__all__ = ("BLUEPRINTS", "core", "import_app")

BLUEPRINTS = (Path(__file__).parent.parent.parent / "blueprints").resolve()

core = Manager(f"<b>Proper v{__version__}", catch_errors=False)


class CantFindApp(Exception):
    pass


def import_app():
    cwd = os.getcwd()
    sys.path.insert(0, cwd)
    from main import app
    return app
