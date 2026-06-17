import typing as t

import inflection

from ..helpers import BLUEPRINTS
from ..helpers.render import render_blueprint


if t.TYPE_CHECKING:
    from ..app import App


CHANNEL_BLUEPRINT = BLUEPRINTS / "channel"


def gen_channel(
    app: "App",
    name: str,
    *,
    force: bool = False,
    _name_pascal: str = "",
    _name_snake: str = "",
) -> None:
    """Stubs a new channel class

    Arguments:
        name:
            The PascalCased name, always singular.
        force [False]:
            Whether to overwrite existing files without asking.

    """
    name_pascal = _name_pascal or inflection.camelize(name)
    name_snake = _name_snake or inflection.underscore(name)

    render_blueprint(
        CHANNEL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.name,
            "name_snake": name_snake,
            "name_pascal": name_pascal,
        },
        force=force,
    )
