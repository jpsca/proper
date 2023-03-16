__all__ = (
    "InmutableDictMixin",
)


class InmutableDictMixin(dict):
    def __setitem__(self, *args):
        raise TypeError("Read-only")

    def __delitem__(self, *args):
        raise TypeError("Read-only")

    def clear(self):
        raise TypeError("Read-only")

    def pop(self, *args):
        raise TypeError("Read-only")

    def popitem(self):
        raise TypeError("Read-only")

    def update(self, *args, **kw):
        raise TypeError("Read-only")
