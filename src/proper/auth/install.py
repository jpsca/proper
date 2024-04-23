import typing as t

from proper.helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    append_routes,
    call,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper import App


AUTH_BLUEPRINT = BLUEPRINTS / "auth"
ROUTES_TT = "routes.tt.py"

DEPENDENCIES = [
    "argon2-cffi",
    "confusable_homoglyphs",
]

SORT_IMPORTS_IN = [
    "views/app.py",
    "config/app.py",
    "cl/__init__.py",
]


def install(app: "App") -> None:
    """Install user/password authentication support.
    """
    bp = BlueprintRender(
        AUTH_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
        },
        ignore=[ROUTES_TT],
    )
    breakpoint()
    bp()

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    routes_tt = AUTH_BLUEPRINT / ROUTES_TT
    new_routes = bp.render.string(routes_tt.read_text())
    append_routes(app, new_routes)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "users"')
