__all__ = (
    "LOCAL_HOSTS",
    "match",
)


LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def match(request, response, app):
    """Match the request url to a route."""
    host = request.host
    if host in LOCAL_HOSTS:
        host = None
    route, params = app.router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params
