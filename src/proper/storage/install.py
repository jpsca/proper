import typing as t

from ..helpers import BLUEPRINTS
from ..helpers.render import (
    add_dependencies,
    call,
    echo,
    render_blueprint,
    sort_imports_in,
)
from ..metadata import record_install


if t.TYPE_CHECKING:
    from ..app import App


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"

SORT_IMPORTS_IN = [
    "controllers/__init__.py",
    "config/storage.py",
]

DEPENDENCIES = [
    "pyvips >= 2.2.3",
]


def install(app: "App") -> None:
    """Install storage support."""
    echo("install", "Storage addon")

    render_blueprint(
        STORAGE_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "storage"')
    record_install(app, "storage")
