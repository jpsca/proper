from importlib import import_module

import inflection


__all__ = ("dispatch",)


def dispatch(request, response, app):
    route = request.matched_route
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_module(route.to.__module__)
    Controller = getattr(module, cls_name)

    response.snake_controller = inflection.underscore(cls_name)
    # Even if we might not use it, let set the inferred template name now
    # (unless is already set), so the action can overwrite it if they want.
    # The template doesn't have a extension so the user can choose to use
    # the default template name but changing the response format from the
    # default, for example, using ".json" instead of ".html".
    response.template = (
        response.template or f"{response.snake_controller}/{action_name}"
    )

    # We instantiate the controller class so we can have an independent
    # container for this request.
    controller = Controller(request=request, response=response, app=app)
    controller._dispatch(action_name)
    response.dispatched = True
