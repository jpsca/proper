import hecto

from proper.helpers import BLUEPRINTS, pascal_to_snake


def controller(app, name, *actions):
    """Stubs out a new controller and its templates.

        bin/manage g controller NAME [action ...]

    Pass the PascalCased model name, and an optional list of actions as arguments.

    """
    source = BLUEPRINTS / "controller"
    data = {
        "class_name": name,
        "snake_name": pascal_to_snake(name),
        "actions": actions or ["index"]
    }
    hecto.copy(source, app.root_path, data=data)
