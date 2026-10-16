import copy
import typing as t


__all__ = ("DotDict",)

# Values `copy.copy()` and `copy.deepcopy()` return as they are
_ATOMS = frozenset({str, int, float, bool, bytes, type(None)})


class DotDict(dict):
    """A dict that:

    - Allows `obj.foo` in addition to `obj['foo']`
    - Improves `update()` method for deep updating.
    """

    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        super().__init__()
        if (
            len(args) == 1 and not kwargs and type(self) is DotDict
            and isinstance(args[0], dict)
        ):
            _fill(self, args[0], deep=False)
        else:
            self.update(*args, **kwargs)

    def __setattr__(self, name: str, value: t.Any) -> None:
        if name.startswith("__"):
            return super().__setattr__(name, value)

        return self.__setitem__(name, value)

    def __getattr__(self, name: str) -> t.Any:
        if name.startswith("__"):
            return super().__getattribute__(name)

        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError(name) from None

    def __setitem__(self, key: object, value: t.Any) -> None:
        if isinstance(value, dict):
            value = self.__class__(value)
        super().__setitem__(key, value)

    def copy(self) -> "DotDict":
        if type(self) is DotDict:
            new = DotDict()
            _fill(new, self, deep=False)
            return new
        return self.__class__(super().copy())

    def update(self, *args, **kwargs) -> None:
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


def _fill(target: DotDict, src: dict, *, deep: bool) -> None:
    """Fill an empty `DotDict` from `src` as `update()` does, without its
    general case: a dict value becomes a deep copy, as a `DotDict`; any other,
    a copy (`deep`: a deep copy). Values that copying returns as they are
    are not copied.

    A session is built with this, and copied, on every request that has one.
    """
    for key, value in src.items():
        if isinstance(value, dict):
            nested = DotDict()
            _fill(nested, value, deep=True)
            value = nested
        elif type(value) not in _ATOMS:
            value = copy.deepcopy(value) if deep else copy.copy(value)
        dict.__setitem__(target, key, value)
