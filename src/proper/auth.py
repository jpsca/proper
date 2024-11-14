import typing as t

from proper.helpers.render import (
    BLUEPRINTS,
    BlueprintRender,
    add_dependencies,
    call,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper import App


AUTH_BLUEPRINT = BLUEPRINTS / "auth"

DEPENDENCIES = [
    "argon2-cffi",
    "confusable-homoglyphs",
]

SORT_IMPORTS_IN = [
    "app.py",
    "controllers/app.py",
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
    )
    bp()

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "users"')
