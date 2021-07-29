from ..constants import GET, HEAD


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get(req, resp, app):
    """Transform a HEAD request to a fake GET request.
    """
    if req.method == HEAD:
        req.real_method = HEAD
        req.method = GET


def strip_body_if_head(req, resp, app):
    """Strip the response body if the method was HEAD.
    """
    if req.real_method == "HEAD":
        resp.body = ""
