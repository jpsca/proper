from importlib import import_module
from typing import TYPE_CHECKING

import inflection

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

    # Even if we might not use it, let set the inferred component name now
    # (unless is already set), so the action can overwrite it if they want.
    response.component = (
        response.component or f"{cls_name}{inflection.camelize(action_name)}"
    )

    # We instantiate the controller class so we can have an independent
    # container for this request.
    controller = Controller(request=request, response=response, app=app)
    controller._dispatch(action_name)
    response.dispatched = True
