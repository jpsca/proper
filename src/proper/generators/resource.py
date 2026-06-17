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
    force: bool = False,
) -> None:
    """Stubs out a new resource including a controller, form, views, and a model.

    proper g resource NAME
        [--only=action[,action]] [--exclude=action[,action]]
        [--namespace=NS_NAME] [--pk=object_id] [--singular] [--migration]
        [attrs...]

    For detailed information run:

    - `proper g controller --help`, and
    - `proper g model --help`

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
        force=force,
        _name_pascal=name_pascal,
        _name_snake=name_snake,
    )

    gen_model(
        app,
        name,
        *attrs,
        migration=migration,
        force=force,
        _name_pascal=name_pascal,
        _name_snake=name_snake,
    )

    if migration:
        call(f'proper db create "{name_snake}"')
