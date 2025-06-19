import datetime
import json
import typing as t


__all__ = ("dumps", "loads")

DATE_PREFIX = "__dt__"


class CustomEncoder(json.JSONEncoder):
    def default(self, o: t.Any) -> str:
        if isinstance(o, datetime.date):
            return f"{DATE_PREFIX}{o.isoformat()}"
        return super().default(o)


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kw) -> None:
        kw["object_hook"] = self.try_datetime
        super().__init__(*args, **kw)

    @staticmethod
    def try_datetime(d: dict) -> dict:
        ret = {}
        for key, value in d.items():
            if isinstance(value, str) and value.startswith(DATE_PREFIX):
                try:
                    value = datetime.datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            ret[key] = value
        return ret


def dumps(
    obj: t.Any,
    *,
    skipkeys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = True,
    indent: int | None = None,
    separators: tuple[str, str] | None = None,
    default: t.Callable[[t.Any], t.Any] | None = None,
    sort_keys: bool = False,
    **kw,
) -> str:
    """Serialize `obj` to a JSON formatted `str` including datetime values.

    If `skipkeys` is true then `dict` keys that are not basic types
    (`str`, `int`, `float`, `bool`, `None`) will be skipped
    instead of raising a `TypeError`.

    If `ensure_ascii` is false, then the return value can contain non-ASCII
    characters if they appear in strings contained in `obj`. Otherwise, all
    such characters are escaped in JSON strings.

    If `check_circular` is false, then the circular reference check
    for container types will be skipped and a circular reference will
    result in an `RecursionError` (or worse).

    If `allow_nan` is false, then it will be a `ValueError` to
    serialize out of range `float` values (`nan`, `inf`, `-inf`) in
    strict compliance of the JSON specification, instead of using the
    JavaScript equivalents (`NaN`, `Infinity`, `-Infinity`).

    If `indent` is a non-negative integer, then JSON array elements and
    object members will be pretty-printed with that indent level. An indent
    level of 0 will only insert newlines. `None` is the most compact
    representation.

    If specified, `separators` should be an `(item_separator, key_separator)`
    tuple.  The default is `(', ', ': ')` if *indent* is `None` and
    `(',', ': ')` otherwise.  To get the most compact JSON representation,
    you should specify `(',', ':')` to eliminate whitespace.

    `default(obj)` is a function that should return a serializable version
    of obj or raise TypeError. The default simply raises TypeError.

    If *sort_keys* is true (default: `False`), then the output of
    dictionaries will be sorted by key.
    """
    kw["cls"] = CustomEncoder
    return json.dumps(
        obj,
        skipkeys=skipkeys,
        ensure_ascii=ensure_ascii,
        check_circular=check_circular,
        allow_nan=allow_nan,
        indent=indent,
        separators=separators,
        default=default,
        sort_keys=sort_keys,
        **kw,
    )


def loads(
    s: str | bytes | bytearray,
    *,
    object_hook: t.Callable[[dict], t.Any] | None = None,
    object_pairs_hook: t.Callable[[list[tuple[t.Any, t.Any]]], t.Any] | None = None,
    parse_float: t.Callable[[str], t.Any] | None = None,
    parse_int: t.Callable[[str], t.Any] | None = None,
    parse_constant: t.Callable[[str], None] | None = None,
    **kw,
) -> t.Any:
    """Deserialize `s` (a `str`, `bytes` or `bytearray` instance
    containing a JSON document) to a Python object.

    `object_hook` is an optional function that will be called with the
    result of any object literal decode (a `dict`). The return value of
    `object_hook` will be used instead of the `dict`. This feature
    can be used to implement custom decoders (e.g. JSON-RPC class hinting).

    `object_pairs_hook` is an optional function that will be called with the
    result of any object literal decoded with an ordered list of pairs.  The
    return value of `object_pairs_hook` will be used instead of the `dict`.
    This feature can be used to implement custom decoders.  If `object_hook`
    is also defined, the `object_pairs_hook` takes priority.

    `parse_float`, if specified, will be called with the string
    of every JSON float to be decoded. By default this is equivalent to
    float(num_str). This can be used to use another datatype or parser
    for JSON floats (e.g. decimal.Decimal).

    `parse_int`, if specified, will be called with the string
    of every JSON int to be decoded. By default this is equivalent to
    int(num_str). This can be used to use another datatype or parser
    for JSON integers (e.g. float).

    `parse_constant`, if specified, will be called with one of the
    following strings: -Infinity, Infinity, NaN.
    This can be used to raise an exception if invalid JSON numbers
    are encountered.

    """
    kw["cls"] = CustomDecoder
    return json.loads(
        s,
        object_hook=object_hook,
        object_pairs_hook=object_pairs_hook,
        parse_float=parse_float,
        parse_int=parse_int,
        parse_constant=parse_constant,
        **kw,
    )
