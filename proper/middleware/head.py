from ..constants import GET, HEAD


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get(request, response, app):
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


def strip_body_if_head(request, response, app):
    """Strip the response body if the method was HEAD."""
    if request.request_method == HEAD:
        response.body = ""
