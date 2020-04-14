import collections


__all__ = ("FrozenDict", )


class FrozenDict(collections.Mapping):
    """
    An immutable wrapper around dictionaries.
    """

    def __init__(self, wrapped, name=None):
        self._dict = wrapped
        if name is not None:
            self.__class__.__name__ = name

    def __getitem__(self, key):
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def copy(self, **add_or_replace):
        return self.__class__(self, **add_or_replace)

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return self._dict.__repr__()

    def __hash__(self):
        return self._dict.__hash__()
