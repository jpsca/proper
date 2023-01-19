from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = ("dispatch",)


def dispatch(request: "Request", response: "Response", app: "App") -> None:
    route = request.matched_route
    assert route
    assert route.to
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_module(route.to.__module__)
    Controller = getattr(module, cls_name)

    # We instantiate the controller class so we can have an independent
    # container for this request.
    controller = Controller(request=request, response=response, app=app)
    controller._dispatch(action_name)
    response.dispatched = True
