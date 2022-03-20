from collections.abc import Iterable


def is_iterable(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))
