import typing as t

from proper.helpers import import_string


if t.TYPE_CHECKING:
    from proper import Request, Response
    from proper import View as BaseView

    from ..app import App


__all__ = ("dispatch",)


def dispatch(app: "App", request: "Request", response: "Response") -> "Response | None":
    route = request.matched_route
    assert route
    assert route.to
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_string(route.to.__module__)
    View: t.Type[BaseView] = getattr(module, cls_name)

    # We instantiate the view class so we can have an independent
    # container for this request.
    view = View(app, request, response)
    view._dispatch(action_name)
