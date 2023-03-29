"""Auto-import all the classes in this folder."""

from proper import find_classes

classes = {
    cls.__name__: cls
    for cls in find_classes(__file__, prefix=__name__)
}
globals().update(classes)
