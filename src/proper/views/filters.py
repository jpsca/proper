"""
minijx runtime: Jinja's builtin filters, minus `xmlattr`, `pprint` and `urlize`.

Every function takes the filtered value first, then the filter's arguments,
exactly as Jinja passes them. Filters that in Jinja need the environment or
the context are rewritten without it, and produce the same output as a
default `jinja2.Environment`. `join` and `replace` are the only ones that
depend on autoescape; `FILTERS_AE` has their autoescape versions.
"""

import json as _json
import math
import random as _random
import re
import typing as t
from collections import abc
from itertools import groupby as _groupby

from .runtime import UNDEFINED, Markup, escape, getattr_, soft_str
from .tests import TESTS  # tests.py imports this module only inside a function


__all__ = [
    "abs", "attr", "batch", "capitalize", "center", "count", "d", "default",
    "dictsort", "e", "escape", "filesizeformat", "first", "float", "forceescape",
    "format", "groupby", "indent", "int", "items", "join", "last", "length",
    "list", "lower", "map", "max", "min", "random", "reject", "rejectattr",
    "replace", "reverse", "round", "safe", "select", "selectattr", "slice",
    "sort", "string", "striptags", "sum", "title", "trim", "truncate", "unique",
    "upper", "urlencode", "wordcount", "wordwrap", "tojson",
]

_builtin_abs = abs
_builtin_float = float
_builtin_int = int
_builtin_list = list
map_ = map
_builtin_max = max
_builtin_min = min
_builtin_round = round
_builtin_sum = sum

_word_re = re.compile(r"\w+")
_striptags_re = re.compile(r"(<!--.*?-->|<[^>]*>)")
_ws_re = re.compile(r"\s+")


def _ignore_case(value: t.Any) -> t.Any:
    return value.lower() if isinstance(value, str) else value


def _make_attrgetter(attribute, postprocess=None, default=None):
    """Same as jinja2.filters.make_attrgetter, using getattr_ for lookups."""
    parts = _prepare_attribute_parts(attribute)

    def attrgetter(item):
        for part in parts:
            item = getattr_(item, part, default)
        if postprocess is not None:
            item = postprocess(item)
        return item

    return attrgetter


def _make_multi_attrgetter(attribute, postprocess=None):
    if isinstance(attribute, str):
        split = attribute.split(",")
    else:
        split = [attribute]
    parts = [_prepare_attribute_parts(item) for item in split]

    def attrgetter(item):
        items = [None] * len(parts)
        for i, attribute_part in enumerate(parts):
            item_i = item
            for part in attribute_part:
                item_i = getattr_(item_i, part, None)
            if postprocess is not None:
                item_i = postprocess(item_i)
            items[i] = item_i
        return items

    return attrgetter


def _prepare_attribute_parts(attr):
    if attr is None:
        return []
    if isinstance(attr, str):
        return [_builtin_int(x) if x.isdigit() else x for x in attr.split(".")]
    return [attr]


# ---------------------------------------------------------------------------


def abs(value):
    return _builtin_abs(value)


def attr(obj, name):
    """Jinja's `attr` only does getattr, never getitem."""
    try:
        return getattr(obj, name)
    except AttributeError:
        return None


def batch(value, linecount, fill_with=None):
    tmp = []
    for item in value:
        if len(tmp) == linecount:
            yield tmp
            tmp = []
        tmp.append(item)
    if tmp:
        if fill_with is not None and len(tmp) < linecount:
            tmp += [fill_with] * (linecount - len(tmp))
        yield tmp


def capitalize(s):
    return soft_str(s).capitalize()


def center(value, width=80):
    return soft_str(value).center(width)


def default(value, default_value="", boolean=False):
    """
    Like Jinja's: replaces a missing value (`UNDEFINED`, which the compiler
    passes for a missing global, attribute or item) and, with `boolean=True`,
    any falsy one. A real `None` is kept, as in Jinja.
    """
    if value is UNDEFINED or (boolean and not value):
        return default_value
    return value


d = default


def dictsort(value, case_sensitive=False, by="key", reverse=False):
    if by == "key":
        pos = 0
    elif by == "value":
        pos = 1
    else:
        raise ValueError('You can only sort by either "key" or "value"')

    def sort_func(item):
        v = item[pos]
        if not case_sensitive:
            v = _ignore_case(v)
        return v

    return sorted(value.items(), key=sort_func, reverse=reverse)


e = escape


def forceescape(value):
    """Escape even what is already markup."""
    if hasattr(value, "__html__"):
        value = value.__html__()
    return escape(str(value))


def filesizeformat(value, binary=False):
    bytes_ = _builtin_float(value)
    base = 1024 if binary else 1000
    prefixes = [
        ("KiB" if binary else "kB"),
        ("MiB" if binary else "MB"),
        ("GiB" if binary else "GB"),
        ("TiB" if binary else "TB"),
        ("PiB" if binary else "PB"),
        ("EiB" if binary else "EB"),
        ("ZiB" if binary else "ZB"),
        ("YiB" if binary else "YB"),
    ]
    if bytes_ == 1:
        return "1 Byte"
    elif bytes_ < base:
        return f"{_builtin_int(bytes_)} Bytes"
    else:
        for i, prefix in enumerate(prefixes):
            unit = base ** (i + 2)
            if bytes_ < unit:
                return f"{base * bytes_ / unit:.1f} {prefix}"
        return f"{base * bytes_ / unit:.1f} {prefix}"


def first(seq):
    try:
        return next(iter(seq))
    except StopIteration:
        return None


def float(value, default=0.0):
    try:
        return _builtin_float(value)
    except (TypeError, ValueError):
        return default


def format(value, *args, **kwargs):
    if args and kwargs:
        raise TypeError("can't handle positional and keyword arguments at the same time")
    return soft_str(value) % (kwargs or args)


class _GroupTuple(t.NamedTuple):
    grouper: t.Any
    list: t.List[t.Any]


def groupby(value, attribute, default=None, case_sensitive=False):
    expr = _make_attrgetter(
        attribute,
        postprocess=_ignore_case if not case_sensitive else None,
        default=default,
    )
    rv = [_GroupTuple(key, _builtin_list(values)) for key, values in _groupby(sorted(value, key=expr), expr)]
    if not case_sensitive:
        # Jinja: the grouper is the first item's original (not lowercased) value
        output_expr = _make_attrgetter(attribute, default=default)
        rv = [_GroupTuple(output_expr(values[0]), values) for _, values in rv]
    return rv


def indent(s, width=4, first=False, blank=False):
    if isinstance(width, str):
        indention = width
    else:
        indention = " " * width
    newline = "\n"
    if isinstance(s, Markup):
        indention = Markup(indention)
        newline = Markup(newline)
    s += newline  # this quirk is necessary for splitlines method
    if blank:
        rv = (newline + indention).join(s.splitlines())
    else:
        lines = s.splitlines()
        rv = lines.pop(0)
        if lines:
            rv += newline + newline.join(indention + line if line else line for line in lines)
    if first:
        rv = indention + rv
    return rv


def int(value, default=0, base=10):
    try:
        if isinstance(value, str):
            return _builtin_int(value, base)
        return _builtin_int(value)
    except (TypeError, ValueError):
        try:
            return _builtin_int(_builtin_float(value))
        except (TypeError, ValueError, OverflowError):
            return default


def items(value):
    if value is None:
        return
    if not isinstance(value, abc.Mapping):
        raise TypeError("Can only get item pairs from a mapping.")
    yield from value.items()


def join(value, d="", attribute=None):
    if attribute is not None:
        value = map_(_make_attrgetter(attribute), value)
    return str(d).join(str(x) for x in value)


def join_ae(value, d="", attribute=None):
    """`join` with autoescape, as Jinja's: when an item is markup, the
    others and the separator are escaped and the result is markup."""
    if attribute is not None:
        value = map_(_make_attrgetter(attribute), value)
    if hasattr(d, "__html__"):
        return soft_str(d).join(map_(soft_str, value))
    value = _builtin_list(value)
    has_markup = False
    for idx, item in enumerate(value):
        if hasattr(item, "__html__"):
            has_markup = True
        else:
            value[idx] = str(item)
    return (escape(d) if has_markup else str(d)).join(value)


def last(seq):
    try:
        return next(iter(reversed(seq)))
    except StopIteration:
        return None


def length(value):
    return len(value)


count = length


def list(value):
    return _builtin_list(value)


def lower(s):
    return soft_str(s).lower()


def _lookup(table: dict, name: str, kind: str) -> t.Callable:
    try:
        return table[name]
    except KeyError:
        raise KeyError(f"No {kind} named {name!r}") from None


def _prepare_map(args, kwargs, filters):
    if not args and "attribute" in kwargs:
        attribute = kwargs.pop("attribute")
        default = kwargs.pop("default", None)
        if kwargs:
            raise TypeError(f"Unexpected keyword argument {next(iter(kwargs))!r}")
        return _make_attrgetter(attribute, default=default)
    try:
        name = args[0]
        args = args[1:]
    except LookupError:
        raise TypeError("map requires a filter argument") from None
    func = _lookup(filters, name, "filter")
    return lambda item: func(item, *args, **kwargs)


def _map(value, args, kwargs, filters):
    if value:
        func = _prepare_map(args, kwargs, filters)
        for item in value:
            yield func(item)


def max(value, case_sensitive=False, attribute=None):
    key_func = _make_attrgetter(attribute, postprocess=_ignore_case if not case_sensitive else None)
    return _builtin_max(value, key=key_func, default=None)


def min(value, case_sensitive=False, attribute=None):
    key_func = _make_attrgetter(attribute, postprocess=_ignore_case if not case_sensitive else None)
    return _builtin_min(value, key=key_func, default=None)


def random(seq):
    return _random.choice(seq)


def _prepare_select_or_reject(args, kwargs, modfunc, lookup_attr, tests):
    if lookup_attr:
        try:
            attr_ = args[0]
        except LookupError:
            raise TypeError("Missing parameter for attribute name") from None
        transfunc = _make_attrgetter(attr_)
        off = 1
    else:
        off = 0

        def transfunc(x):
            return x

    try:
        name = args[off]
    except LookupError:
        return lambda item: modfunc(bool(transfunc(item)))
    args = args[1 + off :]
    test = _lookup(tests, name, "test")
    return lambda item: modfunc(test(transfunc(item), *args, **kwargs))


def _select_or_reject(value, args, kwargs, modfunc, lookup_attr, tests):
    if value:
        func = _prepare_select_or_reject(args, kwargs, modfunc, lookup_attr, tests)
        for item in value:
            if func(item):
                yield item


def _keep(x):
    return x


def _drop(x):
    return not x


def bound_to(filters: dict, tests: dict) -> dict:
    """
    `map`, `select`, `reject`, `selectattr` and `rejectattr`, looking the
    filter or test they are given by name up in these dicts. The module's own
    are bound to the builtin dicts; a catalog with custom filters or tests
    binds its own set (see environment.py), as Jinja's see custom ones.
    """

    def map(value, *args, **kwargs):
        return _map(value, args, kwargs, filters)

    def select(value, *args, **kwargs):
        return _select_or_reject(value, args, kwargs, _keep, False, tests)

    def reject(value, *args, **kwargs):
        return _select_or_reject(value, args, kwargs, _drop, False, tests)

    def selectattr(value, *args, **kwargs):
        return _select_or_reject(value, args, kwargs, _keep, True, tests)

    def rejectattr(value, *args, **kwargs):
        return _select_or_reject(value, args, kwargs, _drop, True, tests)

    return {
        "map": map,
        "select": select,
        "reject": reject,
        "selectattr": selectattr,
        "rejectattr": rejectattr,
    }


def replace(s, old, new, count=None):
    if count is None:
        count = -1
    return str(s).replace(str(old), str(new), count)


def replace_ae(s, old, new, count=None):
    """`replace` with autoescape, as Jinja's: markup in `old` or `new`
    escapes a plain `s` first, so the result is markup."""
    if count is None:
        count = -1
    if hasattr(old, "__html__") or hasattr(new, "__html__") and not hasattr(s, "__html__"):
        s = escape(s)
    else:
        s = soft_str(s)
    return s.replace(soft_str(old), soft_str(new), count)


def reverse(value):
    if isinstance(value, str):
        return value[::-1]
    try:
        return reversed(value)
    except TypeError:
        try:
            rv = _builtin_list(value)
            rv.reverse()
            return rv
        except TypeError:
            raise TypeError("argument must be iterable") from None


def round(value, precision=0, method="common"):
    if method not in {"common", "ceil", "floor"}:
        raise ValueError("method must be common, ceil or floor")
    if method == "common":
        return _builtin_round(value, precision)
    func = getattr(math, method)
    return func(value * (10**precision)) / (10**precision)


def safe(value):
    return Markup(value)


def slice(value, slices, fill_with=None):
    seq = _builtin_list(value)
    length_ = len(seq)
    items_per_slice = length_ // slices
    slices_with_extra = length_ % slices
    offset = 0
    for slice_number in range(slices):
        start = offset + slice_number * items_per_slice
        if slice_number < slices_with_extra:
            offset += 1
        end = offset + (slice_number + 1) * items_per_slice
        tmp = seq[start:end]
        if fill_with is not None and slice_number >= slices_with_extra:
            tmp.append(fill_with)
        yield tmp


def sort(value, reverse=False, case_sensitive=False, attribute=None):
    key_func = _make_multi_attrgetter(attribute, postprocess=_ignore_case if not case_sensitive else None)
    return sorted(value, key=key_func, reverse=reverse)


def string(value):
    return soft_str(value)


def striptags(value):
    if hasattr(value, "__html__"):
        value = value.__html__()
    value = _striptags_re.sub("", str(value))
    value = _unescape_html(value)
    return " ".join(value.split())


def _unescape_html(s):
    import html

    return html.unescape(s)


def sum(iterable, attribute=None, start=0):
    if attribute is not None:
        iterable = map_(_make_attrgetter(attribute), iterable)
    return _builtin_sum(iterable, start)


def title(s):
    return "".join(
        [item[0].upper() + item[1:].lower() for item in _word_beginning_split_re.split(str(s)) if item]
    )


_word_beginning_split_re = re.compile(r"([-\s({\[<]+)")


def trim(value, chars=None):
    return soft_str(value).strip(chars)


def truncate(s, length=255, killwords=False, end="...", leeway=5):
    assert length >= len(end), f"expected length >= {len(end)}, got {length}"
    assert leeway >= 0, f"expected leeway >= 0, got {leeway}"
    if len(s) <= length + leeway:
        return s
    if killwords:
        return s[: length - len(end)] + end
    result = s[: length - len(end)].rsplit(" ", 1)[0]
    return result + end


def unique(value, case_sensitive=False, attribute=None):
    getter = _make_attrgetter(attribute, postprocess=_ignore_case if not case_sensitive else None)
    seen = set()
    for item in value:
        key = getter(item)
        if key not in seen:
            seen.add(key)
            yield item


def upper(s):
    return soft_str(s).upper()


def urlencode(value):

    if isinstance(value, str) or not isinstance(value, abc.Iterable):
        return _url_quote(value)
    if isinstance(value, dict):
        items_ = value.items()
    else:
        items_ = value
    return "&".join(f"{_url_quote(k, for_qs=True)}={_url_quote(v, for_qs=True)}" for k, v in items_)


def _url_quote(obj, charset="utf-8", for_qs=False):
    from urllib.parse import quote

    if not isinstance(obj, bytes):
        if not isinstance(obj, str):
            obj = str(obj)
        obj = obj.encode(charset)
    safe = b"" if for_qs else b"/"
    rv = quote(obj, safe)
    if for_qs:
        rv = rv.replace("%20", "+")
    return rv


def wordcount(s):
    return len(_word_re.findall(str(s)))


def wordwrap(s, width=79, break_long_words=True, wrapstring=None, break_on_hyphens=True):
    import textwrap

    if wrapstring is None:
        wrapstring = "\n"
    return wrapstring.join(
        [
            wrapstring.join(
                textwrap.wrap(
                    line,
                    width=width,
                    expand_tabs=False,
                    replace_whitespace=False,
                    break_long_words=break_long_words,
                    break_on_hyphens=break_on_hyphens,
                )
            )
            for line in s.splitlines()
        ]
    )


def tojson(value, indent=None):
    """
    Same as Jinja's: keys sorted (its default `json.dumps_kwargs` policy is
    `{"sort_keys": True}`), and the replacements that make the result safe
    inside <script>.
    """
    return Markup(
        _json.dumps(value, indent=indent, sort_keys=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("'", "\\u0027")
    )


_NAMED = ("map", "select", "reject", "selectattr", "rejectattr")

FILTERS = {name: globals()[name] for name in __all__ if name not in _NAMED}
FILTERS["escape"] = escape
FILTERS["e"] = escape

_bound = bound_to(FILTERS, TESTS)
FILTERS.update(_bound)
map, select, reject, selectattr, rejectattr = (_bound[name] for name in _NAMED)

# What components compiled with autoescape look filters up in.
FILTERS_AE = {**FILTERS, "join": join_ae, "replace": replace_ae}
FILTERS_AE.update(bound_to(FILTERS_AE, TESTS))
