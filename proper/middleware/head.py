"""
## proper.middleware.head

"""
from ..constants import HEAD, GET


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get(req, resp, _app):
    """Transform a HEAD request to a fake GET request.
    """
    if not resp.dispatched and req.method == HEAD:
        req.real_method = HEAD
        req.method = GET


def strip_body_if_head(req, resp, _app):
    """Strip the response body if the method was HEAD.
    """
    if resp.dispatched and req.real_method == "HEAD":
        resp.headers["Content-Length"] = 0
        resp.body = ""
