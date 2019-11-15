"""
## proper.iplugs.head

"""
from ..constants import HEAD, GET


__all__ = ("head", )


def head(req, resp, _app):
    """Transform a HEAD request to a fake GET request
    and strip the resulting body.
    """
    if not resp.dispatched and req.method == HEAD:
        req.real_method = HEAD
        req.method = GET

    if resp.dispatched and req.real_method == "HEAD":
        resp.headers["Content-Length"] = 0
        resp.body = ""
