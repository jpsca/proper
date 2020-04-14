from os import path

from ..support import objectify, pascal_to_snake


__all__ = ("dispatch",)


def dispatch(req, resp, app):
    route = req.matched_route
    controller, method = objectify(app.controllers_mod, route.to)

    # Even if we might not use it, let set the inferred template name now
    # (unless is already set), so the client can overwrite it if they want.
    if resp.template is None:
        set_template(resp, route)

    run_pipeline(controller._plugs, req, resp, app)
    if resp.stop:
        resp.dispatched = True
        return

    if not resp.dispatched:
        call(controller, method, req, resp, req.matched_params)

    run_pipeline(controller._plugs, req, resp, app)


def run_pipeline(plugs, req, resp, app):
    for plug in plugs:
        if resp.stop:
            break
        plug(req, resp, app)


def set_template(resp, route):
    to = route.to.__qualname__ if callable(route.to) else route.to
    cls_name, method_name = to.split(".")
    folder_name = pascal_to_snake(cls_name)
    file_name = method_name.lower()
    resp.template = path.join(folder_name, file_name)


def call(controller, method, req, resp, params):
    # We call the endpoint but we do not expect a result value.
    # All the side effects of this call should be stored in the same
    # controller and in `resp`.
    method(req, resp, **params)
    resp.dispatched = True

    # If resp.body was manually set, our work here is done.
    if resp.has_body or resp.stop:
        return

    # Otherwise, is template time...
    # `_render()` is a method all controllers MUST have implemented
    resp.body = controller._render(req, resp)
