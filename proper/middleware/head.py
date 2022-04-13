from typing import TYPE_CHECKING
from ..constants import GET, HEAD

if TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = ("head_to_get", "strip_body_if_head")


def head_to_get(request: "Request", response: "Response", app: "App") -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


def strip_body_if_head(request: "Request", response: "Response", app: "App") -> None:
    """Strip the response body if the method was HEAD."""
    if request.request_method == HEAD:
        response.body = ""
