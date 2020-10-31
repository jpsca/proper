import copy


__all__ = ("Dot", )


class Dot(dict):
    """A dict that:

    1. Allows `obj.foo` in addition to `obj['foo']` and
       `obj.foo.bar` in addition to `obj['foo']['bar']`.
    2. Can normalize keys with the optional methods `_key_encode`.
    3. Improved `update()` method for deep updating and key normalization.

    Examples:

    >>> d = Dot({'a': 1, 'b': 2, 'foo': {'b': {'a': 'r'}} })
    >>> d.a
    1
    >>> d.foo
    {'b': {'a': 'r'}}
    >>> d.foo.b.a
    'r'

    """

    def __init__(self, dict_or_iter=None, **kwargs):
        super().__init__()
        self.update(dict_or_iter, **kwargs)

    def _key_encode(self, key):
        return key

    def __setattr__(self, key, value):
        if key.startswith("_"):
            return super().__setattr__(key, value)
        raise AttributeError(
            """Use the obj[key] = value notation to set or update values."""
        )

    def __getattr__(self, key):
        return self.__getitem__(key)

    def __getitem__(self, key):
        key = self._key_encode(key)
        value = super().__getitem__(key)
        if isinstance(value, dict):
            return self.__class__(value)
        return value

    def __setitem__(self, key, value):
        key = self._key_encode(key)
        super().__setitem__(key, value)

    def __delitem__(self, key):
        key = self._key_encode(key)
        super().__delitem__(key)

    def __contains__(self, key):
        return self._key_encode(key) in super().keys()

    def keys(self):
        return (self._key_encode(key) for key in super().keys())

    def setdefault(self, key, default=None):
        key = self._key_encode(key)
        return super().setdefault(key, default)

    def get(self, key, default=None):
        key = self._key_encode(key)
        value = super().get(key, default)
        if isinstance(value, dict):
            return self.__class__(value)
        return value

    def update(self, src=None, **kwargs):
        if src is None:
            return
        if not hasattr(src, "items"):
            src = dict(src)
        self._deepupdate(self, src)

    def _deepupdate(self, target, src):
        """Deep update target dict with src.

        For each k,v in src: if k doesn't exist in target, it is deep copied from
        src to target. Otherwise, if v is a dict, recursively deep-update it.

        """
        for key, value in src.items():
            key = self._key_encode(key)
            if isinstance(value, dict):
                if key not in target:
                    dict.__setitem__(target, key, copy.deepcopy(value))
                else:
                    self._deepupdate(dict.__getitem__(target, key), value)
            else:
                dict.__setitem__(target, key, copy.copy(value))
