from pathlib import Path

from proper.helpers import pascal_to_snake
from proper.helpers.render import BLUEPRINTS, BlueprintRender, extend_routes


ROUTES_TMPL = """,[% for action in actions %]
    get("[[ action ]]", to="[[ pascal_name ]].[[ action ]]"),[% endfor %]
]

"""


def controller(app, name, *actions):
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
        BLUEPRINTS / "controller",
        app.root_path,
        context={
            "pascal_name": name,
            "snake_name": snake_name,
            "actions": actions or ["index"],
        },
    )
    bp()

    new_routes = bp.render.string(ROUTES_TMPL)
    extend_routes(app, new_routes)

    relpath = Path("templates") / snake_name
    templates = app.root_path / relpath
    templates.mkdir(parents=False, exist_ok=True)

    src_relpath = "template.html.jinja"
    for action in actions:
        dst_relpath = relpath / f"{action}.html.jinja"
        bp._render_file(src_relpath, dst_relpath)
