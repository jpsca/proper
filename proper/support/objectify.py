import importlib

__all__ = ("objectify",)


def objectify(module_name, to):
    if callable(to):
        cls_name, method_name = to.__qualname__.split(".")
        module = importlib.import_module(to.__module__)
    else:
        cls_name, method_name = to.split(".")
        module = importlib.import_module(module_name)
    Controller = getattr(module, cls_name)
    # Instantiate the controllers class so we can have an independent
    # container for this request.
    controller = Controller()
    method = getattr(controller, method_name)

    return controller, method
