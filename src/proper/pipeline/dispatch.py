from typing import TYPE_CHECKING

from ..helpers import import_string
from ..current import request, response

if TYPE_CHECKING:
    from proper import Response


__all__ = ("dispatch",)


def dispatch() -> "Response | None":
    route = request.matched_route
    assert route
    assert route.to
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_string(route.to.__module__)
    Controller = getattr(module, cls_name)

    # We instantiate the controller class so we can have an independent
    # container for this request.
    controller = Controller(request, response)
    return controller._dispatch(action_name)
