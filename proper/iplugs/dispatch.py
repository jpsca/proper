"""
## proper.iplugs.dispatch

"""
from os import path

from ..support import objectify, pascal_to_snake


__all__ = ("dispatch", )


def dispatch(req, resp, app):
    run_pipeline(req, resp, app)
    dispatch_to_endpoint(req, resp, app)
    run_pipeline(req, resp, app)


def run_pipeline(req, resp, app):
    pipeline = req.matched_route.pipeline
    for plug in pipeline:
        if resp.stop:
            break
        plug(req, resp, app)


def dispatch_to_endpoint(req, resp, app):
    if resp.stop:
        return
    route = req.matched_route
    controller, method = objectify(route.to, app.controllers_mod)

    # Even if we might not use it, let set the inferred template name now
    # (unless is already set), so the client can overwrite it if they want.
    if resp.template is None:
        set_template(resp, route)

    call(controller, method, req, resp, req.matched_params)


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
    if resp.has_body:
        return

    # Otherwise, is template time...
    # `_render()` is a method all controllers MUST have implemented
    resp.body = controller._render(req, resp)
