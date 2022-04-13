from collections.abc import Mapping
from typing import Any, Iterable


__all__ = ("FrozenDict",)


class FrozenDict(Mapping):
    """An immutable wrapper around dictionaries."""

    def __init__(self, wrapped: dict, name="", error="") -> None:
        self._dict = wrapped
        if name:
            self.__class__.__name__ = name
        self._error = error or self.__class__.__name__ + " is read-only"

    def __getitem__(self, key: str) -> "Any":
        return self._dict[key]

    def __contains__(self, key: str) -> bool:
        return key in self._dict

    def copy(self, **add_or_replace) -> "Any":
        return self.__class__(self, **add_or_replace)

    def __iter__(self) -> "Iterable":
        return iter(self._dict)

    def __len__(self) -> int:
        return len(self._dict)

    def __repr__(self) -> str:
        return self._dict.__repr__()

    def __hash__(self) -> "Any":
        return self._dict.__hash__()

    def __delitem__(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def __setitem__(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def clear(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def pop(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def popitem(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def setdefault(self, *args, **kw) -> None:
        raise AttributeError(self._error)

    def update(self, *args, **kw) -> None:
        raise AttributeError(self._error)
