import typing as t

from ..helpers import BLUEPRINTS
from ..helpers.render import render_blueprint, sort_imports_in


if t.TYPE_CHECKING:
    from ..app import App


CHANNELS_BLUEPRINT = BLUEPRINTS / "channels"

SORT_IMPORTS_IN = [
    "config/__init__.py",
]


def install(app: "App") -> None:
    """Install Channels support."""
    render_blueprint(
        CHANNELS_BLUEPRINT,
        app.root_path.parent,
        context={"app_name": app.name},
    )

    for filename in SORT_IMPORTS_IN:
        sort_imports_in(app.root_path / filename)
