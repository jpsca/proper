from pathlib import Path

import hecto
from pyceo import Cli

from proper.helpers import pascal_to_snake


BLUEPRINTS = (Path(__file__).parent.parent.parent  / "blueprints").resolve()


class GeneratorsCli(Cli):
    _description = ""

    def controller(self, app_root, name):
        """Adds a new controller.

        app_root: root folder of the application
        name: PascalCased name of the controller class"
        """
        source = BLUEPRINTS / "controller"
        data = {
            "class_name": name,
            "snake_name": pascal_to_snake(name),
        }
        hecto.copy(source, app_root, data=data)
