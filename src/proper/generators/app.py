import os
import sys
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
        _install_dependencies(path)
    _wrap_up(path)


def _install_dependencies(path: Path) -> None:
    version_info = sys.version_info
    py = f"{version_info.major}.{version_info.minor}"

    os.chdir(str(path))
    call(f"uv venv --seed -p {py}")
    os.environ["VIRTUAL_ENV"] = str(path / ".venv")
    call(f"uv pip compile --all-extras {path}/pyproject.toml -o {path}/requirements-dev.txt")
    call(f"uv pip compile --extra=test {path}/pyproject.toml -o {path}/requirements-test.txt")
    call(f"uv pip compile {path}/pyproject.toml -o {path}/requirements.txt")
    call(f"uv pip install -r {path}/requirements-dev.txt")
    call("tailwindcss_install")


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
    print("   $ proper run")
    print()
