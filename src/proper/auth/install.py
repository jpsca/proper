import typing as t

from ..helpers import BLUEPRINTS
from ..helpers.render import (
    add_dependencies,
    add_to_concerns,
    call,
    echo,
    render_blueprint,
    sort_imports_in,
)
from ..metadata import record_install


if t.TYPE_CHECKING:
    from ..app import App


AUTH_BLUEPRINT = BLUEPRINTS / "auth"

SORT_IMPORTS_IN = [
    "main.py",
    "controllers/__init__.py",
    "controllers/app_controller.py",
    "cli/__init__.py",
    "emails/__init__.py",
]

DEPENDENCIES = [
    "passlib",
    "argon2-cffi",
    "confusable-homoglyphs",
]


def install(app: "App") -> None:
    """Install user/password authentication support.
    """
    echo("install", "Auth addon")

    render_blueprint(
        AUTH_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )
    add_to_concerns(
        app.root_path / "controllers" / "app_controller.py",
        "Authentication",
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "users"')
    record_install(app, "auth")
