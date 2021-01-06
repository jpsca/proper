import os
import sys
from pathlib import Path

import hecto
from properconf.cli import setup
from properconf.secrets import new_master_key_file
from pyceo import echo


__all__ = ("BLUEPRINTS", "PROJECT_BLUEPRINT", "SetupMixin")

BLUEPRINTS = (Path(__file__).parent.parent.parent / "blueprints").resolve()
PROJECT_BLUEPRINT = BLUEPRINTS / "project"

def _call(cmd):
    echo("   <cmd>running</cmd>  " + cmd)
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
        self._setup_secrets(path)
        print()
        if install_deps:
            deps_installed = self._install_dependencies(path, _prompt=_prompt)
        else:
            deps_installed = False
        self._wrap_up(path, deps_installed)

    def _copy_blueprint(self, path, force):
        data = {"name": path.name}
        hecto.copy(PROJECT_BLUEPRINT, path, data=data, force=force)

    def _setup_secrets(self, path):
        config_path = path / path.name / "config"
        master_key = new_master_key_file(config_path)
        setup.secrets(config_path / "development", master_key=master_key, quiet=True)
        setup.secrets(config_path / "production", master_key=master_key, quiet=True)

    def _install_dependencies(self, path, _prompt=True):
        name = path.stem
        if _prompt and not hecto.utils.prompt_bool(
            f" Install dependencies in a virtualenv at {name}/.venv ?", default=True,
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

    def _wrap_up(self, path, deps_installed):
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
