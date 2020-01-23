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


def import_app(ignore_error=False):
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    try:
        from main import main
        return main.app
    except ImportError:
        if ignore_error:
            return None
        raise


def get_app_root():
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    from main import main
    return Path(main.__file__).parent
