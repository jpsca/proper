import typing as t

from ..helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    append_routes,
    call,
    sort_imports,
)

if t.TYPE_CHECKING:
    from proper import App


AUTH_BLUEPRINT = BLUEPRINTS / "auth"
ROUTES_TT = "routes.tt.py"
APPLICATION_CONTROLLER = "controllers/app.py"
CONFIG_PATH = "config/app.py"

DEPENDENCIES = [
    "argon2-cffi",
    "confusable_homoglyphs",
]


def install(app: "App", migration=True) -> None:
    """Install user/password authentication support.
    Use `--migration` to generate a migration for creating
    the users table.
    """
    curr_appc = app.root_path / APPLICATION_CONTROLLER
    if not curr_appc.is_file():
        raise ValueError(f"{str(curr_appc)} not found")

    code = sort_imports(curr_appc.read_text())
    curr_appc.write_text(code)

    bp = BlueprintRender(
        AUTH_BLUEPRINT,
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

    routes_tt = AUTH_BLUEPRINT / ROUTES_TT
    new_routes = bp.render.string(routes_tt.read_text())
    append_routes(app, new_routes)

    for dep_name in DEPENDENCIES:
        call(f"poetry add {dep_name}")

    if migration:
        call('proper db create "users"')
