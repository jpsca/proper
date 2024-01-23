import typing as t

from .route import Route


__all__ = (
    "Scope",
    "scope",
)


def flatten(ll: t.Iterable) -> list:
    """
    Flatten a list of lists and items into a list of items, without sublists
    Examples:

    >>> flatten([[1, 2, 3], 4, [5]])
    [1, 2, 3, 4, 5]
    >>> flatten([1, 2, 3, 4, 5])
    [1, 2, 3, 4, 5]
    >>> flatten([[1, 2, 3, 4, 5]])
    [1, 2, 3, 4, 5]
    >>> flatten([[], 1])
    [1]
    >>> flatten([[1, [2, 3]], 4, [5]])
    [1, 2, 3, 4, 5]

    """
    result = []
    for item in ll:
        if isinstance(item, list):
            result += flatten(item)
        else:
            result.append(item)
    return result


class Scope:
    r"""
    A Scope is a convenient shortcut to set a prefix and a host to a group
    of routes.

    Arguments are:

    mount (str):
        Prefix for all routes under this scope. Can contain placeholders
        like `:name` or `:name<format>` where "format" can be:

        - nothing, for matching anything except slashes
        - `int` or `float`, for matching numbers
        - `path`, for matching anything *including* slashes
        - a regular expression

        Note that declaring a format doesn't make type conversions, **all values
        are passed to the view as strings**.

        Examples:

        - `docs/:lang<en|es|pt>`
        - `questions/:uuid`
        - `:year<int>/:month<int>`
        - `:year<\d{4}>/:month<\d{2}>`

    host (str):
        Optional. Host for all routes under this scope, including any subdomain
        and an optional port. Examples: "www.example.com", "localhost:5000".

        Like `mount`, it can contain placeholders like `:name` or `:name<format>`
        with the same format rules.

        Examples:

        - :lang<en|es|pt>.example.com
        - :username.localhost:5000

    """
    __slots__ = (
        "mount",
        "host",
    )

    mount: str
    host: str | None

    def __init__(self, mount: str, *, host: str | None = None) -> None:
        self.mount = "/" + mount.strip("/")
        self.host = host

    def __call__(self, *routes) -> list[Route]:
        _routes = []
        for route in flatten(routes):
            self._mount_route(route)
            _routes.append(route)

        return _routes

    def _mount_route(self, route: Route) -> None:
        assert isinstance(
            route, Route
        ), "A scope only can work over instances of `route`."
        if route.path == "/":
            route.path = self.mount
        else:
            route.path = self.mount.rstrip("/") + route.path
        route.host = self.host or route.host

    def __repr__(self) -> str:
        return (
            f"<scope {self.mount}" + (f" host={ self.host}" if self.host else "") + ">"
        )


scope = Scope
