import copy
import typing as t


__all__ = ("DotDict",)


class DotDict(dict):
    """A dict that:

    1. Allows `obj.foo` in addition to `obj['foo']` and
       `obj.foo.bar` in addition to `obj['foo']['bar']`.
    2. Can normalize keys with the optional methods `_key_encode`.
    3. Improved `update()` method for deep updating and key normalization.
    """

    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__()
        self.update(*args, **kwargs)

    def __setattr__(self, name: str, value: t.Any) -> None:
        if name.startswith("__"):
            return super().__setattr__(name, value)

        return self.__setitem__(name, value)

    def __getattr__(self, name: str) -> t.Any:
        if name.startswith("__"):
            return super().__getattribute__(name)

        return self.__getitem__(name)

    def __setitem__(self, key: object, value: t.Any) -> None:
        if isinstance(value, dict):
            value = self.__class__(value)
        super().__setitem__(key, value)

    def copy(self) -> "DotDict":
        return self.__class__(super().copy())

    def update(self, *args, **kwargs) -> None:  # type: ignore
        if args:
            self._update(src=dict(*args), target=self)
        if kwargs:
            self._update(src=kwargs, target=self)

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
