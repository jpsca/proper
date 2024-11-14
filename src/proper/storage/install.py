import typing as t

from ..helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    sort_imports,
)


if t.TYPE_CHECKING:
    from proper import App


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"
CONFIG_PATH = "config/app.py"

DEPENDENCIES = [
    "image-processing-egg",
]


def install(app: "App") -> None:
    """Install storage support.
    """

    bp = BlueprintRender(
        STORAGE_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
        },
    )
    bp()

    config_path = app.root_path / CONFIG_PATH
    code = sort_imports(config_path.read_text())
    config_path.write_text(code)

    add_dependencies(app.root_path, DEPENDENCIES)
