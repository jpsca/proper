from collections.abc import Iterable


__all__ = ("iterable",)


def iterable(obj):
    return isinstance(obj, Iterable) and not isinstance(obj, (str, dict))
