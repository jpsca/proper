import hecto
from pyceo import param

from proper.support import pascal_to_snake

from .core import core, BLUEPRINTS, import_app


__all__ = ("controller",)


@core.command(help="Adds a new controller", group="g")
@param("name", help="PascalCased name of the controller class")
def controller(name):
    source = BLUEPRINTS / "controller"
    app = import_app()
    data = {
        "class_name": name,
        "snake_name": pascal_to_snake(name),
    }
    hecto.copy(source, app.root_path, data=data)
