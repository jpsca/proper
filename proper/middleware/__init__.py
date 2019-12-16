"""Import all *.py files in this folder.
"""
import importlib
import os


for __filename in os.listdir(os.path.dirname(__file__)):  # pragma: no cover
    if __filename.startswith("_") or __filename[-3:] != ".py":
        continue

    __module = importlib.import_module("." + __filename[:-3], __package__)

    if hasattr(__module, "__all__"):
        __all = __module.__all__
    else:
        __all = [name for name in dir(__module) if not name.startswith("_")]

    globals().update({name: getattr(__module, name) for name in __all})
