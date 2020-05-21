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


def import_app():
    try:
        from wsgi import app  # noqa
        return app
    except ImportError as e:
        if e.name != "wsgi":
            raise


def import_cli():
    try:
        from manage import cli  # noqa
        return cli
    except ImportError as e:
        if e.name != "manage":
            raise
        return None


def get_app_root():
    app = import_app()
    return app.root


running_in_app = import_app() is not None
