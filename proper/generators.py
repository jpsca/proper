from pathlib import Path

import hecto

from proper.helpers import pascal_to_snake


BLUEPRINTS = (Path(__file__).parent.parent  / "blueprints").resolve()


def controller(app, name):
    source = BLUEPRINTS / "controller"
    data = {
        "class_name": name,
        "snake_name": pascal_to_snake(name),
    }
    hecto.copy(source, app.root_path, data=data)
