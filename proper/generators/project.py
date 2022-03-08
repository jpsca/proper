import os
import sys
from pathlib import Path

import inflection
from proper_cli import confirm

from ..helpers import BLUEPRINTS, BlueprintRender, call


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
    _wrap_up(path, deps_installed)


def _install_dependencies(path):
    if not confirm(
        f" Install dependencies in a virtualenv at {path.stem}/.venv ?",
        default=True,
    ):
        print()
        return False

    print()
    call(f"{sys.executable or 'python'} -m venv .venv")
    call(".venv/bin/pip install -U pip wheel --quiet")
    call(".venv/bin/pip install -r requirements/dev-requirements.txt")
    call(".venv/bin/pip install -e .")
    call(".venv/bin/proper db create_all")
    call(".venv/bin/proper db stamp")
    call("npm install --no-audit --no-fund")
    return True


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
    print("   $ proper run")
    print()
