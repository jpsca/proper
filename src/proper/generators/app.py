import os
from pathlib import Path

import inflection

from ..helpers import BLUEPRINTS, BlueprintRender, call


APP_BLUEPRINT = BLUEPRINTS / "app"


def gen_app(
    path: str | Path,
    *,
    name: str = "",
    force: bool = False,
    _is_a_test: bool = False,
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

    - path:
        Where to create the new application.

    - name:
        Optional name of the app instead of the one in `path`

    - force:
        Overwrite files that already exist, without asking.

    """
    path = Path(path).resolve().absolute()
    path.mkdir(parents=True, exist_ok=False)
    app_name = inflection.underscore(name or str(path.stem))

    BlueprintRender(
        APP_BLUEPRINT,
        path,
        context={
            "app_name": app_name,
        },
        force=force,
    )()
    print()

    if not _is_a_test:
        _make_bin_files_executable(path / "bin")
        _install_dependencies(path)
    _wrap_up(path)


def _make_bin_files_executable(path: Path) -> None:
    files = [f for f in path.iterdir() if f.is_file()]
    for f in files:
        # equivalent to chmod +x file
        f.chmod(f.stat().st_mode | 0o111)


def _install_dependencies(path: Path) -> None:
    os.chdir(str(path))
    call("python -m venv .venv")
    call(".venv/bin/pip install -U pip wheel --quiet")
    call(".venv/bin/pip install -e ../proper/")  # TODO: remove!
    call("poetry export --without-hashes -f requirements.txt -o requirements.txt --with dev,test")
    call(".venv/bin/pip install -U -r requirements.txt && rm requirements.txt")
    call(".venv/bin/tailwindcss_install")


def _wrap_up(path: Path) -> None:
    print("✨ Done! ✨")
    print()
    print(" The following steps are missing:")
    print()
    print("   $ cd " + path.stem + "")
    print("   $ source .venv/bin/activate")
    print("   $ make db")
    print()
    print(" Start your Proper app with:")
    print()
    print("   $ bin/proper run")
    print()
