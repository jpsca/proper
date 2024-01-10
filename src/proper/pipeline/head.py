from ..constants import GET, HEAD
from ..current import request, response


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get() -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


def strip_body_if_head() -> None:
    """Strip the response body if the method was HEAD."""
    if request.request_method == HEAD:
        response.body = ""
