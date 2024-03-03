import typing as t

from ..helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    append_routes,
    sort_imports,
)


if t.TYPE_CHECKING:
    from proper import App


STORAGE_BLUEPRINT = BLUEPRINTS / "storage"
ROUTES_TT = "routes.tt.py"
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
        ignore=[ROUTES_TT],
    )
    bp()

    config_path = app.root_path / CONFIG_PATH
    code = sort_imports(config_path.read_text())
    config_path.write_text(code)

    routes_tt = STORAGE_BLUEPRINT / ROUTES_TT
    new_routes = bp.render.string(routes_tt.read_text())
    append_routes(app, new_routes)

    add_dependencies(app.root_path, DEPENDENCIES)
