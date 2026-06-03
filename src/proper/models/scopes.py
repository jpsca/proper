import types

import peewee as pw


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


def scope(fn):
    """Tag a method as a scope."""
    fn._is_scope = True
    return fn

