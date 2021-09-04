import os
import sys
from pathlib import Path

import inflection
from pyceo import confirm

from proper.helpers import BLUEPRINTS, BlueprintRender, printf


PROJECT_BLUEPRINT = BLUEPRINTS / "project"


def gen_project(path, *, name=None, force=False, _dependencies=True):
    """Creates a new Proper application at `path`.

    The `proper new` command creates a new Proper application with a default
    directory structure and configuration at the path you specify.

    Examples:

        `proper new ~/Code/blog`
        generates a Proper application at `~/Code/blog`.

        `proper new myapp`
        generates a Proper application at `myapp` in the current folder.

    Arguments:

    - path: Where to create the new application.
    - name [None]: Optional name of the app instead of the one in `path`
    - force [False]: Overwrite files that already exist, without asking.

    """
    path = Path(path).resolve().absolute()
    app_name = inflection.underscore(name or str(path.stem))

    BlueprintRender(
        PROJECT_BLUEPRINT,
        path,
        context={
            "app_name": app_name,
        },
        force=force
    )()
    print()
    os.chdir(str(path))
    deps_installed = _install_dependencies(path) if _dependencies else False
    _make_executables(path)
    _wrap_up(path, deps_installed)


def _call(cmd):
    printf("running", cmd, color="yellow")
    os.system(cmd)


def _install_dependencies(path):
    if not confirm(
        f" Install dependencies in a virtualenv at {path.stem}/.venv ?",
        default=True,
    ):
        print()
        return False

    print()
    _call(f"{sys.executable or 'python'} -m venv .venv")
    _call("source .venv/bin/activate && make setup")
    return True


def _make_executables(path):
    (path / "manage.py").chmod(0o755)


def _wrap_up(path, deps_installed):
    print("✨ Done! ✨")
    print()
    print(" The following steps are missing:")
    print()
    print("   $ cd " + path.stem + "")
    if deps_installed:
        print("   $ source .venv/bin/activate")
    else:
        print("   $ python -m venv .venv")
        print("   $ source .venv/bin/activate")
        print("   $ make setup")
    print()
    print(" Start your Proper app with:")
    print()
    print("   $ make run")
    print()
