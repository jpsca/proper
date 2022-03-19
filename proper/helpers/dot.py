import copy


__all__ = ("Dot",)


class Dot(dict):
    """A dict that:

    1. Allows `obj.foo` in addition to `obj['foo']` and
       `obj.foo.bar` in addition to `obj['foo']['bar']`.
    2. Can normalize keys with the optional methods `_key_encode`.
    3. Improved `update()` method for deep updating and key normalization.
    """

    def __init__(self, dict_or_iter=None, **kwargs):
        super().__init__()
        self.update(dict_or_iter or kwargs)

    def _key_encode(self, key):
        return key

    def __setattr__(self, name, value):
        if name.startswith("__"):
            return super().__setattr__(name, value)

        return self.__setitem__(name, value)

    def __getattr__(self, name):
        if name.startswith("__"):
            return super().__getattribute__(name)

        return self.__getitem__(name)

    def __getitem__(self, key):
        key = self._key_encode(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        key = self._key_encode(key)
        if isinstance(value, dict):
            value = self.__class__(value)
        super().__setitem__(key, value)

    def __delitem__(self, key):
        key = self._key_encode(key)
        super().__delitem__(key)

    def __contains__(self, key):
        return self._key_encode(key) in super().keys()

    def setdefault(self, key, default=None):
        key = self._key_encode(key)
        return super().setdefault(key, default)

    def get(self, key, default=None):
        key = self._key_encode(key)
        return super().get(key, default)

    def update(self, src, *, target=None):
        """Deep update target dict with src.

        For each k,v in src: if k doesn't exist in target, it is deep copied from
        src to target. Otherwise, if v is a dict, recursively deep-update it.

        """
        if not src:
            return
        target = target or self
        if not hasattr(src, "items"):
            src = dict(src)

        for key, value in src.items():
            if isinstance(value, dict):
                if key not in target:
                    target.__setitem__(key, copy.deepcopy(value))
                else:
                    target.update(src=value, target=target.__getitem__(key))
            else:
                target.__setitem__(key, copy.copy(value))
