import typing as t


if t.TYPE_CHECKING:
    from proper import Request, Response

    from ..app import App


__all__ = (
    "LOCAL_HOSTS",
    "match",
)


LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def match(app: "App", request: "Request", _response) -> "Response | None":
    """Match the request url to a route."""
    host: str | None = request.host
    if host in LOCAL_HOSTS:
        host = None
    router = app.router
    route, params = router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params
