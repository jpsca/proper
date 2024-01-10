import typing as t

from ..current import app, request

if t.TYPE_CHECKING:
    from proper import Response


__all__ = (
    "LOCAL_HOSTS",
    "match",
)


LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def match() -> "Response | None":
    """Match the request url to a route."""
    host: str | None = request.host
    if host in LOCAL_HOSTS:
        host = None
    router = app.router
    route, params = router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params
