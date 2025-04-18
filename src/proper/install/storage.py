import typing as t

from proper.helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    call,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper.core.app import App


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"

SORT_IMPORTS_IN = [
    "config/storage.py",
]

DEPENDENCIES = [
    "image-processing-egg",
]


def install(app: "App") -> None:
    """Install storage support."""
    bp = BlueprintRender(
        STORAGE_BLUEPRINT,
        app.root_path.parent,
        context={},
    )
    bp()

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "storage"')
