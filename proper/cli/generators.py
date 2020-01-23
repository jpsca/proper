from pyceo import param
import hecto

from proper.support import pascal_to_snake

from .core import core, BLUEPRINTS, get_app_root


@core.command(help="Adds a new controller", group="g")
@param("name", help="PascalCased name of the controller class")
def controller(name):
    source = BLUEPRINTS / "controller"
    dst = get_app_root()
    data = {
        "class_name": name,
        "snake_name": pascal_to_snake(name),
    }
    hecto.copy(source, dst, data=data)
