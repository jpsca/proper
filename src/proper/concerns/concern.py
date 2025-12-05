import typing as t


if t.TYPE_CHECKING:
    from proper.core.app import App
    from proper.helpers import MultiDict
    from proper.request import Request
    from proper.response import Response


class Concern:
    """Base class for concerns."""

    # Declare attributes to avoid typing errors
    params: "MultiDict"
    defaults: dict
    app: "App"
    request: "Request"
    response: "Response"

    etag = ""

    def before(self):
        getattr(super(), "before", lambda: None)()

    def after(self):
        getattr(super(), "after", lambda: None)()
