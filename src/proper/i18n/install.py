import typing as t

from ..helpers import BLUEPRINTS
from ..helpers.render import (
    add_dependencies,
    add_to_concerns,
    echo,
    render_blueprint,
    sort_imports_in,
)
from ..metadata import record_install


if t.TYPE_CHECKING:
    from ..app import App


I18N_BLUEPRINT = BLUEPRINTS / "i18n"

SORT_IMPORTS_IN = [
    "controllers/app_controller.py",
]
DEPENDENCIES = [
    "babel",
    "poyo",
]


def install(app: "App") -> None:
    """Install internationalization and localization support."""
    echo("install", "i18n addon")

    render_blueprint(
        I18N_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)

    add_to_concerns(
        app.root_path / "controllers" / "app_controller.py",
        "CurrentLocale,",
        "CurrentTimezone,",
        after="Authentication",
    )

    add_dependencies(app.root_path, DEPENDENCIES)
    record_install(app, "i18n")
