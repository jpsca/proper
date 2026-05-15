import typing as t

import inflection

from ..helpers import BLUEPRINTS
from ..helpers.render import render_blueprint


if t.TYPE_CHECKING:
    from ..app import App


EMAIL_BLUEPRINT = BLUEPRINTS / "email"


def gen_email(
    app: "App",
    name: str,
    *attrs: str,
    migration: bool = False,
    _name_pascal: str = "",
    _name_snake: str = "",
) -> None:
    """Stubs a new mailer and templates for it.

    Arguments:
        name:
            The PascalCased name, always singular.
    """
    name_pascal = inflection.camelize(name)
    name_snake = inflection.underscore(name)

    render_blueprint(
        EMAIL_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.name,
            "name_snake": name_snake,
            "name_pascal": name_pascal,
        },
    )
