import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterable, Optional, Union
    TDictOrIter = Optional[Union[dict, Iterable]]

__all__ = ("Dot",)


class Dot(dict):
    """A dict that:

    1. Allows `obj.foo` in addition to `obj['foo']` and
       `obj.foo.bar` in addition to `obj['foo']['bar']`.
    2. Can normalize keys with the optional methods `_key_encode`.
    3. Improved `update()` method for deep updating and key normalization.
    """

    def __init__(
        self,
        dict_or_iter: "TDictOrIter" = None,
        **kwargs
    ) -> None:
        super().__init__()

        dict_or_iter = dict_or_iter or kwargs
        if not hasattr(dict_or_iter, "items"):
            dict_or_iter = dict(dict_or_iter)
        self.update(dict_or_iter)

    def _key_encode(self, key: str) -> str:
        return key

    def __setattr__(self, name: str, value: "Any") -> None:
        if name.startswith("__"):
            return super().__setattr__(name, value)

        return self.__setitem__(name, value)

    def __getattr__(self, name: str) -> "Any":
        if name.startswith("__"):
            return super().__getattribute__(name)

        return self.__getitem__(name)

    def __getitem__(self, key: str) -> "Any":
        key = self._key_encode(key)
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: "Any") -> None:
        key = self._key_encode(key)
        if isinstance(value, dict):
            value = self.__class__(value)
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        key = self._key_encode(key)
        super().__delitem__(key)

    def __contains__(self, key: str) -> bool:
        return self._key_encode(key) in super().keys()

    def setdefault(self, key: str, default: "Any" = None) -> None:
        key = self._key_encode(key)
        return super().setdefault(key, default)

    def get(self, key: str, default: "Any" = None) -> "Any":
        key = self._key_encode(key)
        return super().get(key, default)

    def update(self, src: "TDictOrIter", *, target: "Optional[dict]" = None) -> None:
        """Deep update target dict with src.

        For each k,v in src: if k doesn't exist in target, it is deep copied from
        src to target. Otherwise, if v is a dict, recursively deep-update it.

        """
        if not src:
            return
        if not hasattr(src, "items"):
            src = dict(src)
        if target is None:
            target = self

        for key, value in src.items():
            if key not in target:
                if isinstance(value, dict):
                    target[key] = copy.deepcopy(value)
                else:
                    target[key] = copy.copy(value)
            else:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self.update(src=value, target=target[key])
                else:
                    target[key] = copy.copy(value)
