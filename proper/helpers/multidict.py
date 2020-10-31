from collections import defaultdict


__all__ = ("MultiDict", "exbool", )


class NoValue:
    pass


class MultiDict(defaultdict):
    """A :class:`MultiDict` is a defaultdict subclass customized to deal with
    multiple values for the same key and type casting its values.
    """

    def __init__(self, *mapping):
        super().__init__(list)
        for key, value in mapping or []:
            self[key].append(value)

    def __repr__(self):
        return f"<Multidict {self.keys()}>"

    def get(self, key, default=None, *, type=None, index=-1):
        """Return the last value of the key of `default` one if the key
        doesn't exist.

        If a `type` parameter is provided and is a callable, it should convert
        the value and return it, or raise a :exc:`ValueError` if that is not
        possible, so the function cand return the default as if the key was not
        found.

        >>> d = MultiDict(('foo', '42'), ('bar', 'blub'))
        >>> d.get('foo', type=int)
        42
        >>> d.get('bar', -1, type=int)
        -1

        Arguments are:

            key (str):
                The key to be looked up.

            default (any):
                The default value to be returned if the key can't
                be looked up.  If not further specified `None` is returned.

            type (callable):
                A callable that is used to cast the value in the
                :class:`MultiDict`.  If a :exc:`ValueError` is raised
                by this callable the default value is returned.

            index (int):
                Optional. Get this index instead of the first value

        """
        values = self[key]
        value = values[index] if values else None
        if value is None:
            return default
        if type is not None:
            try:
                return type(value)
            except ValueError:
                return default
        return value

    def get_or_error(self, key, *, type=None, index=-1):
        """Like `.get()` but raises a `KeyError` if the key doesn't exist.
        """
        value = self.get(key, default=NoValue, type=type, index=index)
        if value is NoValue:
            raise KeyError(key)
        return value

    def getall(self, key, *, type=None):
        """Return the list of items for a given key. If that key is not in the
        :class:`MultiDict`, the return value will be an empty list.

        Just as `get` `getlist` accepts a `type` parameter.
        All items will be converted with the callable defined there.
        Those values that return :exc:`ValueError` in the conversion will not
        be included in the final list.

        Arguments are:

            key (str):
                The key to be looked up.

            type (callable):
                A callable that is used to cast the value in the
                :class:`MultiDict`.  If a :exc:`ValueError` is raised
                by this callable the value will be removed from the list.

        """
        values = defaultdict.__getitem__(self, key)
        if type is None:
            return values
        result = []
        for value in values:
            try:
                result.append(type(value))
            except ValueError:
                pass
        return result

    # shallow compatibility with other Request objects
    # Aliases to mimic other multi-dict APIs (Django, Flask, etc.)
    getfirst = get
    getone = get
    getlist = getall


FALSE_STRINGS = ("off", "0", "false", "no")


def exbool(value):
    """Cast a string to boolean considering the empty string as `False`,
    but also the values: `'off'`, `'0'`, `'false'`, `'False'`,
    and `'no'`.
    """
    return bool(value and value.lower() not in FALSE_STRINGS)
