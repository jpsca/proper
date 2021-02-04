from proper.helpers import BLUEPRINTS, pascal_to_snake, render_blueprint

from .helpers import _extend_routes


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

    render_blueprint(
        BLUEPRINTS / "controller",
        app.root_path,
        context={
            "pascal_name": name,
            "snake_name": snake_name,
            "actions": actions or ["index"]
        }
    )
    _extend_routes(app, name, actions)
    templates = app.root_path / "templates" / snake_name
    templates.mkdir(parents=False, exist_ok=True)
    _stub_templates(templates, actions)


def _stub_templates(path, actions):
    source = (BLUEPRINTS / "template.html.jinja").read_text()
    for action in actions:
        action = action.lower()
        (path / f"{action}.html.jinja").write_text(source)
