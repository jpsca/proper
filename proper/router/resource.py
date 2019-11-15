"""
## proper.router.resource

"""
from ..constants import DELETE, GET, PATCH, POST, PUT

from .route import Route


__all__ = ("resource", )


REST_ROUTES = (
    (GET, "/", "index"),
    (GET, "/:uid", "show"),
    (GET, "/new", "new"),
    (POST, "/", "create"),
    (GET, "/:uid/edit", "edit"),
    (PATCH, "/:uid", "update"),
    (PUT, "/:uid", "update"),
    (DELETE, "/:uid", "delete"),
)

REST_ACTIONS = ("index", "show", "new", "create", "edit", "update", "delete")


def resource(path, only=REST_ACTIONS, ignore=None, **kwargs):
    """Shortcut to return a list of HTTP REST routes with the same arguments.

    We calidate the arguments first so we can show errors about what the user has
    typed instead of being about dynamically generated routes.
    """
    assert kwargs.get("to"), "A resource must be created with `to`."
    res = Route("resource", path, **kwargs)

    ignore = ignore or []
    _actions = [
        action
        for action in only
        if (action in REST_ACTIONS) and (action not in ignore)
    ]
    assert _actions, "None of the actions are valid."
    return expand_resource(res, _actions)


def expand_resource(res, actions):
    routes = []
    for method, path, action in REST_ROUTES:
        if action not in actions:
            continue
        route = expand_resource_route(res, method, path, action)
        routes.append(route)
    return routes


def expand_resource_route(res, method, path, action):
    base_path = "/" + res.path.lstrip("/")
    route = Route(
        method,
        base_path.rstrip("/") + path,
        to=expand_to(res.to, action),
        rules=res.rules,
        defaults=res.defaults,
    )
    route.compile_path()
    route.host = res.host
    return route


def expand_to(to, action):
    if callable(to):
        return getattr(to, action)
    return to + "." + action
