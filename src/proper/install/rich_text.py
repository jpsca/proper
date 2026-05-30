import typing as t

from ..helpers import BLUEPRINTS
from ..helpers.render import (
    echo,
    render_blueprint,
    sort_imports_in,
)
from . import storage as storage_installer
from .metadata import is_installed, record_install


if t.TYPE_CHECKING:
    from ..app import App


RICH_TEXT_BLUEPRINT = BLUEPRINTS / "rich_text"

SORT_IMPORTS_IN = [
    "tasks/__init__.py",
]


def install(app: "App") -> None:
    """Install rich text editor support.

    Depends on the storage addon.
    """
    echo("install", "Rich Text addon")

    if not is_installed(app, "storage"):
        storage_installer.install(app)

    render_blueprint(
        RICH_TEXT_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    record_install(app, "rich_text")
