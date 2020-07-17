import os
import sys
from pathlib import Path

import hecto
from pyceo import Manager, param, option
from properconf.cli import setup_secrets, generate_secret_token

from proper.constants import MIN_SECRET_LENGTH
from proper.version import __version__


BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()
PROJECT_BLUEPRINT = BLUEPRINTS / "project"
WELCOME_MSG = f"""
  <b>Proper v{__version__}</b>

  This utility provides commands from Proper itself."""

manager = Manager(WELCOME_MSG, catch_errors=False)


@manager.command(help="Creates a new Proper application at `path`.")
@param("path", help="Where to create the new application.")
@option("force", help="Overwrite files that already exist, without asking.")
def new(path, force=False, _install_deps=True, _prompt=True):
    """The `proper new` command creates a new Proper application with a default
    directory structure and configuration at the path you specify.

    Example: `proper new ~/Code/blog`
    This generates a skeletal Proper application at `~/Code/blog`.
    """
    path = Path(path)
    _copy_blueprint(path, force=force)
    _setup_secrets(path)
    print()
    if _install_deps:
        deps_installed = _install_dependencies(path, _prompt=_prompt)
    else:
        deps_installed = False
    _wrap_up(path, deps_installed)


def _copy_blueprint(path, force):
    data = {"name": path.name}
    hecto.copy(PROJECT_BLUEPRINT, path, data=data, force=force)


def _setup_secrets(path):
    config_path = path / path.name / "config"
    setup_secrets(config_path / "development", quiet=True)
    setup_secrets(config_path / "production", quiet=True)


def _install_dependencies(path, _prompt=True):
    name = path.stem
    if _prompt and not hecto.utils.prompt_bool(
        f" Install dependencies in a virtualenv at {name}/.venv?", default=True,
    ):
        print()
        return False
    print()
    venv = Path(name) / ".venv"
    _call(f"{sys.executable or 'python'} -m venv {venv}")
    pip = venv / "bin" / "pip"
    _call(f"{pip} install -U pip")
    _call(f"{pip} install -e {name}")
    _call(f"{pip} install -r {Path(name) / 'requirements-dev.txt'}")
    # _call(f"cd {name} && npm install")
    return True


def _call(cmd):
    manager.echo("   <cmd>running</cmd>  " + cmd)
    os.system(cmd)


def _wrap_up(path, deps_installed):
    print(" Done! ✨")
    print(" The following steps are missing:")
    print()
    print("   $ cd " + path.stem + "")
    if deps_installed:
        print("   $ source .venv/bin/activate")
    else:
        print("   $ python -m venv .venv")
        print("   $ source .venv/bin/activate")
        print("   $ pip install -e .")
        print("   $ cd web && npm install")
    print()
    print(" Start your Proper app with:")
    print()
    print("   $ python manage.py run")
    print()


@manager.command(help="Returns a secure secret_key")
@option("length")
def secret(length=MIN_SECRET_LENGTH):
    print(generate_secret_token(length))


def manager_run():
    manager.run()


if __name__ == "__main__":
    manager.run()
