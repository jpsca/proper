import types
import typing as t

import peewee as pw


# The scopes of every model class, found once: `dir()` plus a `getattr` per
# attribute is a few hundred calls, and `select()` runs on every page.
# Classes are defined at import time, so there is nothing to invalidate.
_SCOPES: dict[type, dict[str, t.Any]] = {}


class ScopedSelect(pw.ModelSelect):
    """ModelSelect that preserves scopes automatically.

    It adds a little overhead to every method call in exchange
    of a future-proof detection of any query-retuning method.
    However, the overhead is neligible since the queries are built once
    and the real bottleneck will always be the query *execution*.
    """

    _scopes = {}

    def _bind_scopes(self, scopes):
        self._scopes = scopes
        return self

    def __getattribute__(self, name):
        """"""
        # Resolve scopes dynamically so they always bind to the current
        # instance (important after clone() which copies __dict__).
        scopes = super().__getattribute__("_scopes")
        if scopes and name in scopes:
            return types.MethodType(scopes[name], self)

        val = super().__getattribute__(name)

        # Not callable, or is private/class - return as-is
        if name.startswith("_") or not callable(val) or isinstance(val, type):
            return val

        if not scopes:
            return val

        # Wrap the method to propagate scopes to the result
        def wrapper(*args, **kwargs):
            result = val(*args, **kwargs)
            if type(result) is pw.ModelSelect:
                result.__class__ = ScopedSelect
                result._bind_scopes(scopes)
            return result

        return wrapper


class ScopesMixin:
    """Mixin to add scope support to a model."""

    @classmethod
    def _collect_scopes(cls):
        scopes = _SCOPES.get(cls)
        if scopes is None:
            scopes = {}
            for name in dir(cls):
                attr = getattr(cls, name, None)
                if callable(attr) and getattr(attr, "_is_scope", False):
                    scopes[name] = attr
            _SCOPES[cls] = scopes
        return scopes

    @classmethod
    def select(cls, *fields):
        query = super().select(*fields)  # type: ignore
        scopes = cls._collect_scopes()
        if scopes:
            query.__class__ = ScopedSelect
            query._bind_scopes(scopes)
        return query


def scope(fn):
    """Tag a class method as a scope."""
    fn._is_scope = True
    return classmethod(fn)
