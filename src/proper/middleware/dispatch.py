import typing as t

from ..controller import Controller
from ..helpers import import_string


if t.TYPE_CHECKING:
    from ..request import Request
    from ..response import Response


__all__ = ("dispatch",)
TController = type[Controller]


def dispatch(request: "Request", response: "Response") -> "Response | None":
    route = request.matched_route
    assert route
    assert route.to
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_string(route.to.__module__)
    Controller: TController = getattr(module, cls_name)

    # We instantiate the view class so we can have an independent
    # container for this request.
    co = Controller(request, response)
    co._dispatch(action_name)
