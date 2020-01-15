"""
## proper_router.scope

"""
from .base import RE_PARAMS
from .route import Route


__all__ = (
    "Scope",
    "scope",
)


def flatten(ll):
    result = []
    for item in ll:
        if isinstance(item, list):
            result += item
        else:
            result.append(item)
    return result


class Scope(object):
    """
    A Scope is a convenient shortcut to set a prefix and a host to a group
    of routes.

    Arguments are:

        mount (str):
            Prefix for all routes under this scope. Can contain placeholders.

        host (str):
            Optional. Host for all routes under this scope, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        rules (list or tuple):
            Optional. If `mount` contains placeholders, this dict can be used to
            specify the constraints a value must have to match. Without a rule, a
            placeholder will match to everything except slashes.

            ```python
            rules={"<placeholder>": "<constraint>", ...}
            ```

            You can use as constraints regular expressions or one of:
            "int", "float" or "path", that"ll be converted to regular
            expressions for integers, floats or everything *including* slashes.
            Example:

            ```python
            rules={
                "item_id": "int",
                "locales": "(en|es|pt)",
                "path": "path",
                ...
            }
            ```

            Note that this doesn't make type conversions, all values will be passed to
            the controller as strings.

    """

    __slots__ = ("mount", "host", "rules")

    def __init__(self, mount, *, host=None, rules=None):
        self.mount = "/" + mount.strip("/")
        self.host = host

        rules = rules or {}
        # Make sure all params have a key in the rules
        for param in RE_PARAMS.findall(mount):
            rules.setdefault(param, None)
        self.rules = rules

    def __call__(self, *routes):
        routes = flatten(routes)
        _routes = []

        for route in routes:
            self._mount_route(route)
            _routes.append(route)

        return _routes

    def _mount_route(self, route):
        assert isinstance(
            route, Route
        ), "A scope only can work over instances of `proper_router.route`."
        if route.path == "/":
            route.path = self.mount
        else:
            route.path = self.mount.rstrip("/") + route.path
        new_rules = self.rules.copy()
        new_rules.update(route.rules)
        route.rules = new_rules
        route.host = self.host or route.host

    def __repr__(self):
        return (
            f"<scope {self.mount}" + (f" host={ self.host}" if self.host else "") + ">"
        )


scope = Scope
