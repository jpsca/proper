from pathlib import Path

from pyceo import Manager

from proper.version import __version__


__all__ = ("BLUEPRINTS", "core", "import_app")

BLUEPRINTS = (Path(__file__).parent.parent.parent / "blueprints").resolve()

WELCOME_MSG = f"""
  <b>Proper v{__version__}</b>

  This utility provides commands from Proper itself and from
  the application. Loads the application defined in a wsgi.py file."""

core = Manager(WELCOME_MSG, catch_errors=False)


class CantFindApp(Exception):
    pass


def import_app(ignore_error=False):
    try:
        from wsgi import app
        return app
    except ImportError as e:
        if e.name != "wsgi":
            raise
        if ignore_error:
            return None
        raise CantFindApp()


def get_app_root():
    app = import_app()
    return app.root
