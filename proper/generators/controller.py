from pathlib import Path

import inflection

from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = "routes.tmpl.py"
TEMPLATE_TMPL = "template.tmpl.html.jinja"


def gen_controller(app, class_name, *actions):
    """Stubs out a new controller and its templates.

        ./manage.py g controller NAME [action ...]

    Arguments:

    - class_name: The PascalCased controller class name (in plural).
    - actions: Optional list of actions.

    Example:

        ./manage.py g controller Articles index show

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
        ignore=[ROUTES_TMPL, TEMPLATE_TMPL]
    )
    bp()

    template_tmpl = CONTROLLER_BLUEPRINT / TEMPLATE_TMPL
    content = bp.render.string(template_tmpl.read_text())

    (app.root_path / "templates" / snake_name).mkdir(parents=False, exist_ok=True)
    folder = Path(app.root_path.name) / "templates" / snake_name
    for action in actions:
        dst_relpath = folder / f"{action}.html.jinja"
        bp.save_file(content, dst_relpath)

    routes_tmpl = CONTROLLER_BLUEPRINT / ROUTES_TMPL
    new_routes = bp.render.string(routes_tmpl.read_text())
    append_routes(app, new_routes)
