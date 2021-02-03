from proper.helpers import BLUEPRINTS, pascal_to_snake, render_folder


def controller(app, name, *actions):
    """Stubs out a new controller and its templates.

        bin/manage g controller NAME [action ...]

    Pass the PascalCased model name, and an optional list of actions as arguments.

    """
    snake_name = pascal_to_snake(name)
    actions = [pascal_to_snake(action) for action in actions]
    render_folder(
        BLUEPRINTS / "controller",
        app.root_path,
        context={
            "pascal_name": name,
            "snake_name": snake_name,
            "actions": actions or ["index"]
        }
    )

    templates = app.root_path / "templates" / snake_name
    templates.mkdir(parents=False, exist_ok=True)
    _stub_templates(templates, actions)


def _stub_templates(path, actions):
    source = (BLUEPRINTS / "template.html.jinja").read_text()
    for action in actions:
        action = action.lower()
        (path / f"{action}.html.jinja").write_text(source)
