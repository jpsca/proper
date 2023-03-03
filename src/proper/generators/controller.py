from pathlib import Path
from typing import TYPE_CHECKING

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, save_file

if TYPE_CHECKING:
    from proper import App


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
COMPONENT_TT = "component.jinja"
ROUTES_TT = "routes.tt.py"


def gen_controller(app: "App", name: str, *actions: str) -> None:
    """Stubs out a new controller and its components.

        proper g controller NAME [action ...]

    Arguments:

    - name: The PascalCased controller class name (in plural).
    - actions: Optional list of actions.

    Example:

        proper g controller Articles index show

    """
    plural_name = inflection.pluralize(name)
    plural_pascal = inflection.camelize(plural_name)
    plural_snake = inflection.underscore(plural_name)
    actions = tuple([inflection.underscore(action) for action in actions] or ["index"])
    root_path = Path(app.root_path.parent)

    bp = BlueprintRender(
        CONTROLLER_BLUEPRINT,
        root_path,
        context={
            "app_name": app.root_path.name,
            "plural_pascal": plural_pascal,
            "plural_snake": plural_snake,
            "snake_name": plural_snake,
            "actions": actions,
        },
        ignore=[ROUTES_TT, COMPONENT_TT],
    )
    bp()

    component_tt = CONTROLLER_BLUEPRINT / COMPONENT_TT
    content = component_tt.read_text()
    for action in actions:
        action_pascal = inflection.camelize(action)
        save_file(
            root_path,
            f"{app.root_path.name}/components/{plural_pascal}/{action_pascal}.jinja",
            content
        )

    routes_tt = CONTROLLER_BLUEPRINT / ROUTES_TT
    new_routes = bp.render.string(routes_tt.read_text())
    append_routes(app, new_routes)
