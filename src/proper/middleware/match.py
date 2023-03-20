import typing as t

if t.TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = (
    "LOCAL_HOSTS",
    "match",
)


LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def match(request: "Request", response: "Response", app: "App") -> None:
    """Match the request url to a route."""
    host: str | None = request.host
    if host in LOCAL_HOSTS:
        host = None
    route, params = app.router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params
