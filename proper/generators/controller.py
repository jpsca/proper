from pathlib import Path

from proper.helpers import pascal_to_snake
from proper.helpers.render import BLUEPRINTS, BlueprintRender, append_routes


CONTROLLER_BLUEPRINT = BLUEPRINTS / "controller"
ROUTES_TMPL = BLUEPRINTS / "routes.py.generic.tmpl"
TEMPLATE_TMPL = BLUEPRINTS / "template.html.jinja.tmpl"


def gen_controller(app, name, *actions):
    """Stubs out a new controller and its templates.

        bin/manage g controller NAME [action ...]

    Pass the PascalCased controller name (in plural), and an optional list
    of actions as arguments.
    Example:

        bin/manage g controller Articles index show

    """
    snake_name = pascal_to_snake(name)
    actions = [pascal_to_snake(action) for action in actions]

    bp = BlueprintRender(
        CONTROLLER_BLUEPRINT,
        app.root_path.parent,
        context={
            "app_name": app.root_path.name,
            "pascal_name": name,
            "snake_name": snake_name,
            "actions": actions or ["index"],
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
