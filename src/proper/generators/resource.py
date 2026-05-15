from typing import TYPE_CHECKING

import inflection

from ..helpers.render import call
from .controller import gen_controller
from .model import gen_model


if TYPE_CHECKING:
    from ..app import App


def gen_resource(
    app: "App",
    name: str,
    *attrs: str,
    only: str = "",
    exclude: str = "",
    namespace: str = "",
    pk: str = "",
    singular: bool = False,
    migration: bool = False,
) -> None:
    """Stubs out a new resource including a controller, model, form, and views.

    proper g resource NAME
        [--only=action[,action]] [--exclude=action[,action]]
        [--namespace=NS_NAME] [--pk=object_id] [--singular] [--migration]
        [attrs...]

    Run `proper g controller --help` for more information.

    """
    name_pascal = inflection.camelize(name)
    name_snake = inflection.underscore(name)

    gen_controller(
        app,
        name,
        *attrs,
        only=only,
        exclude=exclude,
        namespace=namespace,
        pk=pk,
        singular=singular,
        _name_pascal=name_pascal,
        _name_snake=name_snake,
    )

    gen_model(
        app,
        name,
        *attrs,
        migration=migration,
        _name_pascal=name_pascal,
        _name_snake=name_snake,
    )

    if migration:
        call(f'proper db create "{name_snake}"')
