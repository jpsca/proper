import os
import sys
from pathlib import Path
import inflection
from proper_cli import confirm

from ..helpers import BLUEPRINTS, BlueprintRender, call


PROJECT_BLUEPRINT = BLUEPRINTS / "project"


def gen_project(
    path: str | Path,
    *,
    name: str = "",
    force: bool = False,
    _dependencies: bool = True
) -> None:
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
    path.mkdir(parents=True, exist_ok=False)
    app_name = inflection.underscore(name or str(path.stem))

    BlueprintRender(
        PROJECT_BLUEPRINT,
        path,
        context={
            "app_name": app_name,
        },
        force=force,
    )()
    print()

    _make_bin_files_executable(path/ "bin")
    deps_installed = _install_dependencies(path) if _dependencies else False
    _wrap_up(path, deps_installed)


def _make_bin_files_executable(path: Path) -> None:
    files = [f for f in path.iterdir() if f.is_file()]
    for f in files:
        stat = f.stat().st_mode
        # equivalent to chmod +x file
        f.chmod(f.stat().st_mode | 0o111)


def _install_dependencies(path: Path) -> bool:
    if not confirm(
        f" Install dependencies in a virtualenv at {path.stem}/.venv ?",
        default=True,
    ):
        print()
        return False

    print()
    os.chdir(str(path))
    call(f"{sys.executable or 'python'} -m venv .venv")
    call(".venv/bin/pip install -U pip wheel --quiet")
    call("poetry export --with dev,test -o requirements.txt")
    call(".venv/bin/pip install -r requirements.txt && rm requirements.txt")
    call("npm install --no-audit --no-fund")
    call(".venv/bin/pip install -e ../proper/")
    return True


def _wrap_up(path: Path, deps_installed: bool) -> None:
    print("✨ Done! ✨")
    print()
    print(" The following steps are missing:")
    print()
    print("   $ cd " + path.stem + "")
    if deps_installed:
        print("   $ source .venv/bin/activate")
        print("   $ make db")
    else:
        print("   $ python -m venv .venv")
        print("   $ source .venv/bin/activate")
        print("   $ make install")
    print()
    print(" Start your Proper app with:")
    print()
    print("   $ proper run")
    print()
