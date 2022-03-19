from pathlib import Path

import inflection

from ..helpers.render import BLUEPRINTS, BlueprintRender, append_routes, save_file


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = "routes.tmpl.py"
TEMPLATE_TMPL = "template.tmpl.html.jinja"


def gen_controller(app, name, *actions):
    """Stubs out a new controller and its templates.

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
        ignore=[ROUTES_TMPL, TEMPLATE_TMPL],
    )
    bp()

    template_tmpl = CONTROLLER_BLUEPRINT / TEMPLATE_TMPL
    content = bp.render.string(template_tmpl.read_text())

    (app.root_path / "templates" / plural_snake).mkdir(parents=False, exist_ok=True)
    folder = Path(app.root_path.name) / "templates" / plural_snake
    for action in actions:
        dst_relpath = folder / f"{action}.html.jinja"
        save_file(root_path, dst_relpath, content)

    routes_tmpl = CONTROLLER_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
