from ..constants import DELETE, GET, PATCH, POST, PUT

from .route import Route


__all__ = ("resources", )


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


def resources(path, to, only=REST_ACTIONS, ignore=None, **kwargs):
    """Shortcut to return a list of HTTP REST routes with the same arguments.

    We calidate the arguments first so we can show errors about what the user has
    typed instead of being about dynamically generated routes.
    """
    res = Route("resources", path, to=to, **kwargs)

    ignore = ignore or []
    _actions = [
        action for action in only if (action in REST_ACTIONS) and (action not in ignore)
    ]
    assert _actions, "None of the actions are valid."
    return expand_resources(res, _actions)


def expand_resources(res, actions):
    routes = []
    for method, path, action in REST_ROUTES:
        if action not in actions:
            continue
        route = expand_resources_route(res, method, path, action)
        routes.append(route)
    return routes


def expand_resources_route(res, method, path, action):
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
