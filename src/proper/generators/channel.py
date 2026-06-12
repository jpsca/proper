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
    _name_pascal: str = "",
    _name_snake: str = "",
) -> None:
    """Stubs a new channel class

    Arguments:
        name:
            The PascalCased name, always singular.
    """
    name_pascal = inflection.camelize(name)
    name_snake = inflection.underscore(name)

    render_blueprint(
        CHANNEL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.name,
            "name_snake": name_snake,
            "name_pascal": name_pascal,
        },
    )
