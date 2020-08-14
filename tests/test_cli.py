import os

import pytest
from proper.cli import PROJECT_BLUEPRINT, new


def test_project_blueprint_exists():
    assert PROJECT_BLUEPRINT.is_dir()
    assert (PROJECT_BLUEPRINT / "README.md").is_file()


def test_new(dst):
    dest = dst / "myproject"
    os.mkdir(dest)
    new(dest, _install_deps=False, _prompt=False)
    config_path = dest / "myproject" / "config"

    assert (dest / "README.md").is_file()
    assert (config_path / "development" / "secrets.enc.toml").is_file()
    assert (config_path / "development" / "master.key").is_file()
    assert (config_path / "production" / "secrets.enc.toml").is_file()
    assert (config_path / "production" / "master.key").is_file()


@pytest.mark.skip(reason="too slow")
def test_new_full(dst):
    dest = dst / "myproject"
    os.mkdir(dest)
    new(dest, _prompt=False)

    assert (dest / ".venv").is_dir()
