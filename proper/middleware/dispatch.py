from os import path

from ..support import objectify, pascal_to_snake


__all__ = ("dispatch",)


def dispatch(req, resp, app):
    route = req.matched_route

    # Even if we might not use it, let set the inferred template name now
    # (unless is already set), so the action can overwrite it if they want.
    resp.template = resp.template or get_default_template(resp, route.to)

    Controller, action = objectify(app.controllers_module, route.to)
    # We instantiate the controller class so we can have an independent
    # container for this request.
    controller = Controller()
    controller._dispatch(action, req, resp, app)
    resp.dispatched = True


def get_default_template(resp, endpoint):
    """Return the template basepath using the controller class name
    and the action.

    The template doesn't have a extension so the action can choose to use
    the default template name but changing the response format from the
    default, for example, using ".json" instead of ".html".
    """
    to = endpoint.__qualname__ if callable(endpoint) else endpoint
    cls_name, action = to.split(".")
    folder_name = pascal_to_snake(cls_name)
    file_name = action.lower()
    return path.join(folder_name, file_name)
