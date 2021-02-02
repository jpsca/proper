"""Command Line User Interface for Proper itself.
"""
import os
import sys
from pathlib import Path

from pyceo import Cli, echo, confirm

from proper.helpers import BLUEPRINTS, render_folder
from proper.server import on_start
from proper.version import __version__


__all__ = ("PROJECT_BLUEPRINT", "SetupMixin", "ProperCli")


PROJECT_BLUEPRINT = BLUEPRINTS / "project"

def _call(cmd):
    echo("   <fg:yellow>running</fg>  " + cmd)
    os.system(cmd)


class ProperCli(Cli):
    __doc__ = f"""<b>Proper v{__version__}</b>

    This utility provides commands from Proper itself."""

    def welcome(self, host="0.0.0.0", port=5000):
        """Display the welcome message for the development server.

        Arguments:

        - host [0.0.0.0]
        - port [5000]

        """
        on_start(host=host, port=port)

    def new(self, path, force=False, install_deps=True, _prompt=True):
        """Creates a new Proper application at `path`.

        The `proper new` command creates a new Proper application with a default
        directory structure and configuration at the path you specify.

        Example: `proper new ~/Code/blog`
        This generates a skeletal Proper application at `~/Code/blog`.

        Arguments:

        - path:
            Where to create the new application.
        - force [False]:
            Overwrite files that already exist, without asking.
        - install_deps [True]:
            Create a new virtualenv and install the dependencies of the new app

        """
        path = Path(path)
        self._copy_blueprint(path, force=force)
        print()
        if install_deps:
            deps_installed = self._install_dependencies(path, _prompt=_prompt)
        else:
            deps_installed = False

        self._make_executables(path)
        self._wrap_up(path, deps_installed)

    # Private

    def _copy_blueprint(self, path, force):
        data = {"name": path.name}
        render_folder(PROJECT_BLUEPRINT, path, data=data, force=force)

    def _install_dependencies(self, path, _prompt=True):
        name = path.stem
        if _prompt and not confirm(
            f" Install dependencies in a virtualenv at {name}/.venv ?", default=True,
        ):
            print()
            return False

        print()
        os.chdir(str(path))
        _call(f"{sys.executable or 'python'} -m venv .venv")
        _call(".venv/bin/pip install -U pip wheel")
        _call(".venv/bin/pip install -r requirements/requirements-dev.txt")
        _call(".venv/bin/pip install -e .")
        _call("cd static && npm install")
        return True

    def _make_executables(self, path):
        for child in (path / "bin").iterdir():
            child.chmod(0o755)

    def _wrap_up(self, path, deps_installed):
        print()
        print(" Done! ✨")
        print(" The following steps are missing:")
        print()
        print("   $ cd " + path.stem + "")
        if deps_installed:
            print("   $ source .venv/bin/activate")
        else:
            print("   $ python -m venv .venv")
            print("   $ source .venv/bin/activate")
            print("   $ make install")
        print()
        print(" Start your Proper app with:")
        print()
        print("   $ bin/run")
        print()


cli = ProperCli()
