"""Auto-import all the controllers in this folder and subfolders."""
from inspect import isclass

from proper import Controller, iter_modules_recursive


classes = {}

for module in iter_modules_recursive(__file__, __name__, exclude=("concerns", )):
    for attribute_name in dir(module):
        if not attribute_name[0].isupper():
            continue
        attribute = getattr(module, attribute_name)
        if (
            isclass(attribute)
            and issubclass(attribute, Controller)
            and attribute is not Controller
        ):
            classes[attribute_name] = attribute

globals().update(classes)
