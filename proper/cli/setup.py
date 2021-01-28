import os
import sys
from pathlib import Path

import hecto
from pyceo import echo


__all__ = ("BLUEPRINTS", "PROJECT_BLUEPRINT", "SetupMixin")

BLUEPRINTS = (Path(__file__).parent.parent.parent / "blueprints").resolve()
PROJECT_BLUEPRINT = BLUEPRINTS / "project"

def _call(cmd):
    echo("   <fg:yellow>running</fg>  " + cmd)
    os.system(cmd)


class SetupMixin:
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
        self._wrap_up(path, deps_installed)

    def _copy_blueprint(self, path, force):
        data = {"name": path.name}
        hecto.copy(PROJECT_BLUEPRINT, path, data=data, force=force)

    def _install_dependencies(self, path, _prompt=True):
        name = path.stem
        if _prompt and not hecto.utils.prompt_bool(
            f" Install dependencies in a virtualenv at {name}/.venv ?", default=True,
        ):
            print()
            return False

        print()
        os.chdir(str(path))
        _call(f"{sys.executable or 'python'} -m venv .venv")
        _call(".venv/bin/pip install -U pip wheel")
        _call(".venv/bin/pip install -r requirements/development.txt")
        _call(".venv/bin/pip install -e .")
        _call("cd static && npm install")
        return True

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
