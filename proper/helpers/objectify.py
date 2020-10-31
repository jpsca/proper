from importlib import import_module


__all__ = ("objectify",)


def objectify(module, to):
    if callable(to):
        cls_name, action = to.__qualname__.split(".")
        module = import_module(to.__module__)
    else:
        cls_name, action = to.split(".")
    Controller = getattr(module, cls_name)
    return Controller, action
