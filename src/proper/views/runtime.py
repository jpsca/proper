"""
minijx runtime: helpers the generated code calls.

Everything the compiler emits goes through the names re-exported here, so
generated modules only need `from proper.views.runtime import ...`.
"""

import typing as t

from markupsafe import Markup
from markupsafe import escape as _ms_escape


# markupsafe's own escaping loop, which returns a plain `str` (its public
# `escape` wraps the result in `Markup`, which costs more than the escaping).
# It is private, so there is a fallback; tests/test_runtime.py checks that
# the fast one is found.
try:
    from markupsafe._speedups import _escape_inner
except ImportError:  # pragma: no cover
    try:
        from markupsafe._native import _escape_inner
    except ImportError:

        def _escape_inner(s: str, /) -> str:
            return str(_ms_escape(s))


_MISSING = object()


class _Undefined:
    """
    What `x | default(...)` receives when `x` does not exist: a missing
    global, attribute or item. minijx is otherwise strict and has no
    Undefined; this sentinel exists so `default` can tell "missing" from a
    real `None`, as Jinja does. It never reaches the output: `default`
    always replaces it.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "UNDEFINED"


UNDEFINED = _Undefined()


def escape(value: t.Any) -> Markup:
    """
    The `escape` (`e`) filter: `markupsafe.escape`. Objects with `__html__`
    are kept as they are, and the result is `Markup`, so escaping twice
    does nothing.
    """
    return _ms_escape(value)


def escape_output(value: t.Any, _str=str, _int=int, _escape_inner=_escape_inner) -> str:
    """
    What a `{{ }}` renders in a component compiled with autoescape: the
    value escaped, as a plain `str`, unless it has `__html__`.

    It returns `str` instead of `Markup` because building a `Markup` costs
    more than escaping a short string. `str` and `int`, by far the most
    common values, skip the attribute lookup.
    """
    t_ = type(value)
    if t_ is _str:
        return _escape_inner(value)
    if t_ is _int:
        return _str(value)
    html = getattr(value, "__html__", None)
    if html is not None:
        return html()
    return _escape_inner(_str(value))


def soft_str(value: t.Any) -> str:
    """`str()` that keeps a `str` subclass (`Markup`) as it is, as Jinja's."""
    return value if isinstance(value, str) else str(value)


def concat(*parts: t.Any) -> str:
    """`a ~ b ~ c`: string concatenation with str() applied to each side."""
    return "".join([str(p) for p in parts])


def mconcat(*parts: t.Any) -> str:
    """
    `a ~ b ~ c` with autoescape, as Jinja's `markup_join`: when a part has
    `__html__`, the result is `Markup` and the other parts are escaped;
    otherwise it is a plain `str`, escaped later when it is rendered.
    """
    for part in parts:
        if hasattr(part, "__html__"):
            return Markup("").join([soft_str(p) for p in parts])
    return "".join([str(p) for p in parts])


# Everything `getattr` can find on a plain dict. An instance of exactly `dict`
# has no `__dict__`, so its attributes are only those of the class.
_DICT_ATTRS = frozenset(dir(dict))


def getattr_(obj: t.Any, name: t.Any, default: t.Any = _MISSING) -> t.Any:
    """
    Jinja's `obj.name`: try getattr, then getitem.

    Strict: if neither works and no default was given, raises AttributeError
    instead of returning Undefined.

    Shortcut for plain dicts: when `name` is not an attribute of `dict`, the
    `getattr` is bound to fail, and raising and catching that AttributeError
    costs more than the whole lookup. Going straight to the key gives the same
    result. Subclasses of `dict` take the general path, since they can define
    their own attributes.
    """
    if type(obj) is dict and type(name) is str and name not in _DICT_ATTRS:
        value = obj.get(name, _MISSING)
        if value is not _MISSING:
            return value
        if default is not _MISSING:
            return default
        raise AttributeError(f"'dict' object has no attribute or item {name!r}")
    if isinstance(name, str):
        try:
            return getattr(obj, name)
        except AttributeError:
            pass
    try:
        return obj[name]
    except (TypeError, LookupError, AttributeError):
        pass
    if default is not _MISSING:
        return default
    raise AttributeError(f"{type(obj).__name__!r} object has no attribute or item {name!r}")


def getitem(obj: t.Any, name: t.Any, default: t.Any = _MISSING) -> t.Any:
    """
    Jinja's `obj[name]`: try getitem, then getattr (the opposite order).
    """
    try:
        return obj[name]
    except (TypeError, LookupError, AttributeError):
        pass
    if isinstance(name, str):
        try:
            return getattr(obj, name)
        except AttributeError:
            pass
    if default is not _MISSING:
        return default
    raise AttributeError(f"{type(obj).__name__!r} object has no item or attribute {name!r}")


_ABSENT = object()


def has_attr(obj: t.Any, name: t.Any) -> bool:
    """`obj.name is defined`."""
    return getattr_(obj, name, _ABSENT) is not _ABSENT


class InvalidPropType(TypeError):
    """A component argument annotated with a builtin type (`{# def title: str #}`)
    got a value of another type. Same message as Jx's."""


def merge_attrs(attrs: t.Any, explicit: dict[str, t.Any]) -> dict[str, t.Any]:
    """
    `<Comp attrs={{ attrs }} x=1 />`, as Jx: the forwarded attributes
    (`Attrs` or a dict) and the explicit ones, which win. The component
    takes the ones it declares as arguments; the rest are its `attrs`.
    """
    if isinstance(attrs, Attrs):
        base = attrs.as_dict
    elif attrs:
        base = dict(attrs)
    else:
        base = {}
    return {**base, **explicit}


def invalid_prop(component: str, arg: str, expected: type, value: t.Any) -> t.NoReturn:
    raise InvalidPropType(
        f"{component}: `{arg}` expected {expected.__name__}, got {type(value).__name__}"
    )


class _NoTags:
    """
    What the code of a custom tag finds when the catalog has no function for
    it: the module was compiled with `--tags`, but rendered without them.
    """

    __slots__ = ()

    def __getitem__(self, name: str) -> t.NoReturn:
        raise KeyError(
            f"No function for the tag {{% {name} %}}: pass it to the Catalog, "
            f"`Catalog(..., tags={{{name!r}: function}})`"
        )


NO_TAGS = _NoTags()


# --- Calls of the pure globals (`Catalog(pure=...)`) ---

# The types whose values a call is remembered by: they can't change, and two
# of them that are equal are the same value. Not bool or float: `True == 1`
# and `1.0 == 1`, with the same hash, but they are not the same argument
# (`str(True)` is "True").
_SIMPLE = frozenset({str, int, type(None)})
# Results remembered per module, at most: the values of the arguments come
# from the data (ids), and past this many a call is made each time
MAX_PURE = 4096


def pure_set(cache: dict, site: int, value: t.Any) -> t.Any:
    """Remember the result of a call with constant arguments."""
    cache[site] = value
    return value


def pure_call(cache: dict, site: int, fn: t.Callable, names: tuple, /, *values: t.Any) -> t.Any:
    """`fn(*positional, **keywords)`, where the last `len(names)` of `values`
    are the keywords, remembered by the call site and the values. With a
    value of another type than `_SIMPLE` (an object, whose attributes may
    change, a list...), it is called each time."""
    for v in values:
        if type(v) not in _SIMPLE:
            return _call(fn, names, values)
    key = (site, values)
    value = cache.get(key, _MISSING)
    if value is _MISSING:
        value = _call(fn, names, values)
        if len(cache) < MAX_PURE:
            cache[key] = value
    return value


def _call(fn: t.Callable, names: tuple, values: tuple) -> t.Any:
    if not names:
        return fn(*values)
    n = len(values) - len(names)
    return fn(*values[:n], **dict(zip(names, values[n:], strict=True)))


from .attrs import Attrs  # noqa: E402
from .loop import Loop  # noqa: E402


__all__ = [
    "NO_TAGS", "UNDEFINED", "InvalidPropType", "invalid_prop", "merge_attrs", "Attrs", "Loop", "Markup", "concat", "escape", "escape_output", "getattr_",
    "getitem", "has_attr", "mconcat", "pure_call", "pure_set", "soft_str",
]
