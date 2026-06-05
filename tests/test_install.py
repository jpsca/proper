"""Setup a new app, install its dependencies, generates a resource, install addons,
and run the generated tests on it.
"""
from pathlib import Path


# import proper_new


BLUEPRINT = Path(__file__).parent / "blueprint"


def test_install(tmp_path):
    # base_path = tmp_path / "myapp"

    # proper_new.install(
    #     path=base_path,
    #     name="My App",
    #     src=BLUEPRINT,
    #     force=True,
    #     install_deps=True,
    # )
    # assert (base_path / "app" / "main.py").exists()
    # TBD
    ...
