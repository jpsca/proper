"""Router object that holds all routes and match them to urls.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple

from proper.errors import MatchNotFound, MethodNotAllowed
from .route import Route
from .scope import flatten


__all__ = ("Router", "NameNotFound")


class NameNotFound(Exception):
    pass


class Router:
    _debug: bool
    _routes: List
    _routes_by_name = Dict[str, Route]

    def __init__(self, *, _debug: bool = False) -> None:
        self._routes = []
        self._routes_by_name = {}
        self._debug = _debug

    def match(
        self,
        method: str,
        path: str,
        host: Optional[str] = None,
    ) -> Tuple[Route, Dict[str, Any]]:
        """Takes a method and a path, that came from an URL,
        and tries to match them to a existing route

        Arguments are:

        method:
            Usualy, one of the HTTP methods: "get", "post", "put", "delete",
            "options", or "patch"; but it could also be another
            application-specific value.

        path:
            The path of this route

        host:
            Optional. Host for this route, including any subdomain
            and an optional port. Examples: "www.example.com", "localhost:5000".

        Returns a matched `(route, params)`
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
    def routes(self) -> List[Route]:
        return self._routes

    @routes.setter
    def routes(self, values: Iterable) -> None:
        _routes = flatten(values)
        if self._debug:
            assert all(
                [isinstance(x, Route) for x in _routes]
            ), "All routes must be instances of `Route`."
        for route in _routes:
            route.compile_path()
        self._routes = _routes
        self._routes_by_name = {route.name: route for route in _routes}

    def url_for(
        self,
        name: str,
        object: Optional[Any] = None,
        *,
        _anchor: Optional[str] = None,
        **kwargs: Dict[str, Any]
    ) -> str:
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
