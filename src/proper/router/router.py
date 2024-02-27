"""Router object that holds all routes and match them to urls.
"""
from typing import Any

from proper import current
from proper.errors import MatchNotFound, MethodNotAllowed, RouteNotFound

from .route import Route
from .scope import flatten


__all__ = ("Router",)


class Router:
    __slots__ = ["_debug", "_routes", "_routes_by_name"]

    def __init__(self, *, _debug: bool = False) -> None:
        self._debug = _debug
        self._routes: list[Route] = []
        self._routes_by_name: dict[str, Route] = {}

    def match(
        self,
        method: str,
        path: str,
        host: str | None = None,
    ) -> tuple[Route, dict]:
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
    def routes(self) -> list[Route]:
        return self._routes

    @routes.setter
    def routes(self, values: list[Route]) -> None:
        _routes = flatten(values)
        if self._debug:
            assert all(
                isinstance(x, Route) for x in _routes
            ), "All routes must be instances of `Route`."
        for route in _routes:
            route.compile_path()
        self._routes = _routes
        self._routes_by_name = {route.name: route for route in _routes}

    def url_for(
        self,
        name: str,
        object: Any = None,
        *,
        _anchor: str = "",
        **kw,
    ) -> str:
        if name.startswith("/"):
            return name

        route = self._routes_by_name.get(name)
        if not route:
            raise RouteNotFound(name)

        if object is not None:
            for key in route.path_placeholders:
                kw.setdefault(key, getattr(object, key))

        url = route.format(**kw)

        if _anchor:
            url += "#" + _anchor

        return url

    def url_is(
        self,
        name: str,
        object: Any = None,
        *,
        curr_url: str = "",
        **kw,
    ) -> bool:
        control = self.url_for(name, object, **kw)
        if not curr_url and current.request:
            curr_url = current.request.path
        return curr_url.rstrip("/") == control.rstrip("/")

    def url_startswith(
        self,
        name: str,
        object: Any = None,
        *,
        curr_url: str = "",
        **kw,
    ) -> bool:
        control = self.url_for(name, object, **kw)
        if not curr_url and current.request:
            curr_url = current.request.path
        curr_url = curr_url.rstrip("/")

        if curr_url == control:
            return True
        if curr_url.startswith(f"{control}/"):
            return True
        return False
