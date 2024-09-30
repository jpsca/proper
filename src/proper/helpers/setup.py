from importlib import import_module


def get_instance(**config):
    mod_name, cls_name = config.pop("type").rsplit(".", 1)
    mod = import_module(mod_name)
    Database = getattr(mod, cls_name)
    return Database(**config)
