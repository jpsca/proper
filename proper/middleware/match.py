__all__ = (
    "LOCAL_HOSTS",
    "match",
)


LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def match(req, resp, app):
    """Match the request url to a route.
    """
    host = req.host
    if host in LOCAL_HOSTS:
        host = None
    route, params = app.router.match(req.method, req.path, host)
    req.matched_route = route
    req.matched_params = params
