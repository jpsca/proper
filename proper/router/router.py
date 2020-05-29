"""Router object that holds all routes and match them to urls.
"""
from .route import Route
from .scope import flatten


__all__ = ("Router", "NameNotFound")


class NameNotFound(Exception):
    pass


class Router(object):
    """
    Arguments are:

        host (str):
            Default `host:port`, example: "example.org:5000". Default is "0.0.0.0:3030".
            Used by `url_for` to build an absolute URL if the route doesn't have
            a its host defined.

        root_path (str):
            The root path of the script, default is an empry string.
            Used by `url_for` to build an absolute URL.

        ssl (bool):
            Used by `url_for` to use `https` instead of when building an absolute
            URL. The default is `False`.

        MatchNotFound (Exception):
            Raise thsi exception if a matching endpoint for an URL cannot be found.

        MethodNotAllowed (Exception):
            Raise this exception if a matching endpoint is found, but doesn't allow
            the requested HTTP method.

    """

    __slots__ = (
        "_host",
        "_root_path",
        "use_ssl",
        "MatchNotFound",
        "MethodNotAllowed",
        "_debug",
        "_routes",
        "_by_name",
    )

    def __init__(
        self, *, host="0.0.0.0:3030", root_path="", use_ssl=False,
        MatchNotFound=Exception, MethodNotAllowed=Exception, _debug=False
    ):

        self.host = host
        self.root_path = root_path
        self.use_ssl = bool(use_ssl)
        self.MatchNotFound = MatchNotFound
        self.MethodNotAllowed = MethodNotAllowed

        self._debug = _debug
        self._routes = ()

        # Routes by name
        self._by_name = ()

    @property
    def host(self):
        return self._host

    @host.setter
    def host(self, host):
        self._host = host.rstrip("/")

    @property
    def root_path(self):
        return self._root_path

    @root_path.setter
    def root_path(self, root_path):
        self._root_path = ("/" + root_path.strip("/")).rstrip("/")

    def match(self, method, path, host=None):
        """Takes a method and a path, that came from an URL,
        and tries to match them to a existing route

        Arguments are:

            method(str)
            path (str)
            host (str): Optional

        Returns (tuple):

            A matched `(route, params)` where `route` and `params`
            can be `None` if the route is a forward directive.

        """
        # If the path match but the method do not, we need to return
        # a list of the allowed methods with the 405 response.
        allowed = set([])
        for route in self.routes:
            if route.host != host:
                continue
            match = route.match(path)
            if not match:
                continue
            if route.forward_to is None and route.method != method:
                allowed.add(route.method)
                continue

            if not (route.to or route.forward_to or route.redirect):
                # build-only route
                continue

            params = route.defaults.copy() or {}
            params.update(match.groupdict())

            return route, params

        if allowed:
            msg = f"`{path}` does not accept a `{method}`."
            raise self.MethodNotAllowed(msg, allowed=allowed)
        else:
            msg = f"{method} `{path}` does not match."
            raise self.MatchNotFound(msg)

    @property
    def routes(self):
        return self._routes

    @routes.setter
    def routes(self, values):
        _routes = flatten(values)
        if self._debug:
            assert all(
                [isinstance(x, Route) for x in _routes]
            ), "All routes must be instances of `proper_router.route`."
        for route in _routes:
            route.compile_path()
        self._routes = tuple(_routes)
        self._by_name = {route.name: route for route in _routes}

    def url_for(self, name, *, _external=False, _anchor=None, **kwargs):
        """...
        """
        route = self._by_name.get(name)
        if not route:
            raise NameNotFound(name)

        url = self.root_path + route.format(**kwargs)

        if _anchor:
            url += "#" + _anchor

        if not _external:
            return url

        protocol = ("https" if self.use_ssl else "http") + "://"
        host = route.host or self.host
        return protocol + host + url
