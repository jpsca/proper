from pathlib import Path

import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = BLUEPRINTS / "routes.py.generic.tmpl"
TEMPLATE_TMPL = BLUEPRINTS / "template.html.jinja.tmpl"


def gen_controller(app, class_name, *actions):
    """Stubs out a new controller and its templates.

        bin/manage g controller NAME [action ...]

    Pass the PascalCased controller class_name (in plural), and an optional list
    of actions as arguments.

    Example:

        bin/manage g controller Articles index show

    """
    class_name = inflection.camelize(inflection.pluralize(class_name))
    snake_name = inflection.underscore(class_name)
    actions = [inflection.underscore(action) for action in actions] or ["index"]

    bp = BlueprintRender(
        CONTROLLER_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "class_name": class_name,
            "snake_name": snake_name,
            "actions": actions,
        },
    )
    bp()

    new_routes = bp.render.string(ROUTES_TMPL.read_text())
    append_routes(app, new_routes)

    templates = Path(app.root_path.name) / "templates" / snake_name
    templates.mkdir(parents=False, exist_ok=True)
    content = bp.render.string(TEMPLATE_TMPL.read_text())
    for action in actions:
        dst_relpath = templates / f"{action}.html.jinja"
        bp.save_file(content, dst_relpath)
