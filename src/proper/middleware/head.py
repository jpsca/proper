import typing as t

from ..constants import GET, HEAD


if t.TYPE_CHECKING:
    from ..request import Request
    from ..response import Response


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get(request: "Request", _response) -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


def strip_body_if_head(request: "Request", response: "Response") -> None:
    """Strip the response body if the method was HEAD."""
    if request.request_method == HEAD:
        response.body = ""
