"""
## proper.support.objectify

"""
import importlib

from .inflector import pascal_to_snake
from .inflector import snake_to_pascal


__all__ = ("objectify",)


def objectify(to, package):
    if callable(to):
        cls_name, method_name = to.__qualname__.split(".")
        Controller = import_controller(to.__module__, None, cls_name)
    else:
        cls_name, method_name = to.split(".")
        module = "." + pascal_to_snake(cls_name)
        Controller = import_controller(module, package, cls_name)

    # Instantiate the controllers class so we can have an independent
    # container for this request.
    controller = Controller()
    method = getattr(controller, method_name)

    return controller, method


def import_controller(module, package, name):
    imported = importlib.import_module(module, package=package)
    return getattr(imported, snake_to_pascal(name))
