"""Router object that holds all routes and match them to urls.
"""
from proper.errors import MatchNotFound, MethodNotAllowed
from .route import Route
from .scope import flatten


__all__ = ("Router", "NameNotFound")


class NameNotFound(Exception):
    pass


class Router:
    __slots__ = (
        "_debug",
        "_routes",
        "_routes_by_name",
    )

    def __init__(self, *, _debug=False):
        self._debug = _debug
        self._routes = ()
        self._routes_by_name = ()

    def match(self, method, path, host=None):
        """Takes a method and a path, that came from an URL,
        and tries to match them to a existing route

        Arguments are:

            method(str)
            path (str)
            host (str): Optional

        Returns (tuple):

            A matched `(route, params)`

        """
        # If the path match but the method do not, we need to return
        # a list of the allowed methods with the 405 response.
        allowed = set()
        for route in self.routes:
            if route.host is not None and route.host != host:
                continue
            match = route.match(path)
            if not match:
                continue
            if route.method != method:
                allowed.add(route.method)
                continue

            if not (route.to or route.redirect):
                # build-only route
                continue

            params = route.defaults.copy() or {}
            params.update(match.groupdict())

            return route, params

        if allowed:
            msg = f"`{path}` does not accept a `{method}`."
            raise MethodNotAllowed(msg, allowed=allowed)
        else:
            msg = f"{method} `{path}` does not match."
            raise MatchNotFound(msg)

    @property
    def routes(self):
        return self._routes

    @routes.setter
    def routes(self, values):
        _routes = flatten(values)
        if self._debug:
            assert all(
                [isinstance(x, Route) for x in _routes]
            ), "All routes must be instances of `Route`."
        for route in _routes:
            route.compile_path()
        self._routes = tuple(_routes)
        self._routes_by_name = {route.name: route for route in _routes}

    def url_for(self, name, object=None, *, _anchor=None, **kwargs):
        route = self._routes_by_name.get(name)
        if not route:
            raise NameNotFound(name)

        if object is not None:
            for key in route.path_placeholders:
                kwargs.setdefault(key, getattr(object, key))

        url = route.format(**kwargs)
        if _anchor:
            url += "#" + _anchor

        return url
