import typing as t


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..app import App
    from ..helpers import MultiDict
    from ..request import Request
    from ..response import Response


class Concern:
    """Base class for concerns."""

    etag = ""

    # Declare attributes to avoid typing errors
    params: "MultiDict"
    defaults: dict
    app: "App"
    request: "Request"
    response: "Response"
    _should_run_concern: "Callable[[dict[str, t.Any]], bool]"
