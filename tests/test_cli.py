import os

import pytest
from proper.cli import cli, PROJECT_BLUEPRINT


def test_project_blueprint_exists():
    assert PROJECT_BLUEPRINT.is_dir()
    assert (PROJECT_BLUEPRINT / "README.md").is_file()


@pytest.mark.skip(reason="too slow")
def test_new_full(dst):
    dest = dst / "myproject"
    os.mkdir(dest)
    cli.new(dest, _prompt=False)

    assert (dest / ".venv").is_dir()
