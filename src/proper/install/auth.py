import typing as t

from proper.helpers import BLUEPRINTS
from proper.helpers.render import (
    add_dependencies,
    call,
    render_blueprint,
    sort_imports_in,
)


if t.TYPE_CHECKING:
    from proper.core.app import App


AUTH_BLUEPRINT = BLUEPRINTS / "auth"

SORT_IMPORTS_IN = [
    "main.py",
    "controllers/base.py",
    "cl/__init__.py",
]

DEPENDENCIES = [
    "passlib",
    "argon2-cffi",
    "confusable-homoglyphs",
]


def install(app: "App") -> None:
    """Install user/password authentication support.
    """
    render_blueprint(
        AUTH_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_dependencies(app.root_path, DEPENDENCIES)
    call('proper db create "users"')
