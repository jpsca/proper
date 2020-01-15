from pathlib import Path
import os
import sys

from pyceo import param
from pyceo import option
import hecto

from proper.support import secrets

from .core import core, BLUEPRINTS


__all__ = (
    "PROJECT_BLUEPRINT",
    "new",
)

PROJECT_BLUEPRINT = BLUEPRINTS / "project"


@core.command(help="Creates a new Proper application at `path`.")
@param("path", help="Where to create the new application.")
@option("force", help="Overwrite files that already exist, without asking.")
def new(path, force=False, _install_deps=True, _prompt=True):
    """The `proper new` command creates a new Proper application with a default
    directory structure and configuration at the path you specify.

    Example: `proper new ~/Code/blog`
    This generates a skeletal Proper application at `~/Code/blog`.
    """
    path = Path(path)
    data = {"name": path.name}
    hecto.copy(PROJECT_BLUEPRINT, path, data=data, force=force)
    print()

    _setup_secrets(path)
    if _install_deps:
        deps_installed = _install_dependencies(path, _prompt=_prompt)
    else:
        deps_installed = False
    wrap_up(path, deps_installed)


def _call(cmd):
    core.echo("   <cmd>running</cmd>  " + cmd)
    os.system(cmd)


def _setup_secrets(path):
    print(" Generating secrets for development and production…")
    config_path = path / "config"

    master_key = secrets.new_master_key_file(config_path / "development")
    secrets.save_secrets(
        config_path / "development" / "secrets.yaml.enc",
        secrets.make_dev_default_secrets(),
        master_key=master_key,
    )

    master_key = secrets.new_master_key_file(config_path / "production")
    secrets.save_secrets(
        config_path / "production" / "secrets.yaml.enc",
        secrets.make_prod_default_secrets(),
        master_key=master_key,
    )
    print()


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


def wrap_up(path, deps_installed):
    print(" Done! The following steps are missing:")
    print()
    print("   $ cd " + path.stem + "")
    if deps_installed:
        print("   $ source .venv/bin/activate")
    else:
        print("   $ python -m venv .venv")
        print("   $ source .venv/bin/activate")
        print("   $ pip install -e .")
        print("   $ npm install")
    print()
    print(" Then, configure your database in config/development/config.yaml and run:")
    print()
    print("   $ db_create yourdatabase")
    print()
    print(" Start your Proper app with:")
    print()
    print("   $ proper serve")
    print()
