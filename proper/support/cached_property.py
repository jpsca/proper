__all__ = ("cached_property", )


class cached_property:
    """Decorator to create properties that are computed only once per instance
    and then saved as normal attributes.
    Works for classes with a `__dict__` (no slots).
    """

    def __init__(self, func, on_error_cache=None, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__doc__ = doc or func.__doc__
        self.__module__ = func.__module__
        self.func = func
        self.on_error_cache = on_error_cache

    def __get__(self, obj, type=None):
        try:
            if obj is None:
                return self
            value = obj.__dict__[self.__name__] = self.func(obj)
            return value
        except Exception:
            obj.__dict__[self.__name__] = self.on_error_cache
            raise
