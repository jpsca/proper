from pathlib import Path

import hecto

from proper.helpers import pascal_to_snake


__all__ = ("controller",)

BLUEPRINTS = (Path(__file__).parent.parent / "blueprints").resolve()


def controller(app_root, name):
    """Adds a new controller

    app_root (str/path): root folder of the application
    name (str): PascalCased name of the controller class"
    """
    source = BLUEPRINTS / "controller"
    data = {
        "class_name": name,
        "snake_name": pascal_to_snake(name),
    }
    hecto.copy(source, app_root, data=data)
