import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterable, Optional, Tuple, Union
    TDictOrIter = Optional[Union[dict, Iterable[Tuple[Any, Any]]]]

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
        self.update(dict_or_iter, **kwargs)

    def _key_encode(self, key: object) -> object:
        return key

    def __setattr__(self, name: str, value: "Any") -> None:
        if name.startswith("__"):
            return super().__setattr__(name, value)

        return self.__setitem__(name, value)

    def __getattr__(self, name: str) -> "Any":
        if name.startswith("__"):
            return super().__getattribute__(name)

        return self.__getitem__(name)

    def __getitem__(self, key: object) -> "Any":
        key = self._key_encode(key)
        return super().__getitem__(key)

    def __setitem__(self, key: object, value: "Any") -> None:
        key = self._key_encode(key)
        if isinstance(value, dict):
            value = self.__class__(value)
        super().__setitem__(key, value)

    def __delitem__(self, key: object) -> None:
        key = self._key_encode(key)
        super().__delitem__(key)

    def __contains__(self, key: object) -> bool:
        return self._key_encode(key) in super().keys()

    def setdefault(self, key: object, default: "Any" = None) -> None:
        key = self._key_encode(key)
        return super().setdefault(key, default)

    def get(self, key: object, default: "Any" = None) -> "Any":
        key = self._key_encode(key)
        return super().get(key, default)

    def update(self, dict_or_iter, /, **kw) -> None:  # type: ignore
        if dict_or_iter:
            self._update(src=dict(dict_or_iter), target=self)
        if kw:
            self._update(src=kw, target=self)

    def _update(self, src: dict, target: dict) -> None:
        """Deep update target dict with src.

        For each k,v in src: if k doesn't exist in target, it is deep copied from
        src to target. Otherwise, if v is a dict, recursively deep-update it.

        """
        if not src:
            return
        for key, value in src.items():
            if key not in target:
                if isinstance(value, dict):
                    target[key] = copy.deepcopy(value)
                else:
                    target[key] = copy.copy(value)
            else:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._update(src=value, target=target[key])
                else:
                    target[key] = copy.copy(value)
