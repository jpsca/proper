import typing as t
from collections.abc import ItemsView, KeysView, MutableMapping


__all__ = ("MultiDict",)

TDictOrIter = dict[str, t.Any] | t.Iterable[tuple[str, t.Any]]


class MultiDict(MutableMapping):
    """
    A `MultiDict` is a dict-like type customized to deal with
    multiple values for the same key and type casting its values.
    """

    data: dict[str, list[t.Any]]

    def __init__(
        self,
        dict_or_iter: TDictOrIter = (),
    ) -> None:  # type: ignore
        self.data = {}
        self.update(dict_or_iter)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, key: str):  # type: ignore
        return key in self.data

    def __delitem__(self, key: str):
        del self.data[key]

    def __getitem__(self, key: str):
        return self.data.get(key)

    def __setitem__(self, key: str, value: t.Any):
        return self.append(key, value)

    def __repr__(self):
        return f"{type(self).__name__}({list(self)!r})"

    def keys(self) -> KeysView:
        return self.data.keys()

    def items(self) -> ItemsView:
        return self.data.items()

    def append(self, key: str, value: t.Any) -> None:
        self.data.setdefault(key, []).append(value)

    def extend(self, key: str, values: list[t.Any]) -> None:
        self.data.setdefault(key, []).extend(values)

    def update(self, dict_or_iter: TDictOrIter = ()) -> None:  # type: ignore
        if dict_or_iter:
            if isinstance(dict_or_iter, MultiDict):
                for key, values in dict_or_iter.items():
                    self.data.setdefault(key, []).extend(values)
            elif hasattr(dict_or_iter, "items"):
                for key, value in dict(dict_or_iter).items():
                    self.data.setdefault(key, []).append(value)
            else:
                for key, value in dict_or_iter:
                    self.data.setdefault(key, []).append(value)

    def get(
        self,
        key: str,
        default: t.Any = None,
        *,
        type: t.Callable | None = None,
        index: int = -1,
    ) -> t.Any:
        """Return the last value of the key of `default` one if the key
        doesn't exist.

        If a `type` parameter is provided and is a callable, it should convert
        the value and return it, or raise a :exc:`ValueError` if that is not
        possible, so the function cand return the default as if the key was not
        found.

        >>> d = MultiDict([('foo', '42'), ('bar', 'blub')])
        >>> d.get('foo', type=int)
        42
        >>> d.get('bar', -1, type=int)
        -1

        Arguments are:

            key (str):
                The key to be looked up.

            default (any):
                The default value to be returned if the key can't
                be looked up. If not specified, `None` is used.

            type (callable):
                A callable that is used to cast the value in the
                `MultiDict`. If `ValueError` or `TypeError` are raised,
                the default value is returned.

            index (int):
                Optional. Get this index instead of the first value

        """
        if key not in self.data:
            return default
        value = self.data[key][index]

        if type is not None:
            try:
                return type(value)
            except (TypeError, ValueError):
                return default
        return value

    def getall(
        self,
        key: str,
        *,
        type: t.Callable | None = None,
    ) -> list:
        """Return the list of items for a given key. If that key is not in the
        `MultiDict`, the return value will be an empty list.

        Just as `get`, `getall` accepts a `type` parameter.
        All items will be converted with the callable defined there.
        Those values that return :exc:`ValueError` in the conversion will not
        be included in the final list.

        Arguments are:

            key (str):
                The key to be looked up.

            type (callable):
                A callable that is used to cast the value in the
                `MultiDict`. If `ValueError` or `TypeError` are raised,
                the value is not included in the result

        """
        if key not in self.data:
            return []
        values = self.data[key]
        if type is None:
            return values
        result = []
        for value in values:
            try:
                result.append(type(value))
            except (TypeError, ValueError):
                pass
        return result

    def set(self, key: str, values: list[t.Any]):
        """Replace all values for the given `key`"""
        if not isinstance(values, list):
            values = list(values)
        self.data[key] = values
