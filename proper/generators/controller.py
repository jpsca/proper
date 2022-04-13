from pathlib import Path
from typing import TYPE_CHECKING

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, save_file

if TYPE_CHECKING:
    from typing import List
    from proper import App


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
COMPONENT_TMPL = "component.html.jinja"
ROUTES_TMPL = "routes.tmpl.py"


def gen_controller(app: "App", name: str, *actions: "List[str]") -> None:
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
    actions = [inflection.underscore(action) for action in actions] or ["index"]
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
        ignore=[ROUTES_TMPL, COMPONENT_TMPL],
    )
    bp()

    component_tmpl = CONTROLLER_BLUEPRINT / COMPONENT_TMPL
    content = component_tmpl.read_text()
    for action in actions:
        action_pascal = inflection.camelize(action)
        save_file(
            root_path,
            f"{app.root_path.name}/components/{plural_snake}/{plural_pascal}{action_pascal}.html.jinja",
            content
        )

    routes_tmpl = CONTROLLER_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
