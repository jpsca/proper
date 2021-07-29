from typing import Any, Callable, Dict, Iterable, List, Optional

from .route import Route


__all__ = ["resource", ]


GROUP_ROUTES = (
    ("GET", "/", "index"),
    ("GET", "/new", "new"),
    ("POST", "/", "create"),
    ("GET", "/:uid", "show"),
    ("GET", "/:uid/edit", "edit"),
    ("PATCH", "/:uid", "update"),
    ("PUT", "/:uid", "update"),
    ("DELETE", "/:uid", "delete"),
)
SINGLE_ROUTES = (
    ("GET", "/new", "new"),
    ("POST", "/", "create"),
    ("GET", "/", "show"),
    ("GET", "/edit", "edit"),
    ("PATCH", "/", "update"),
    ("PUT", "/", "update"),
    ("DELETE", "/", "delete"),
)
ACTIONS = ("index", "new", "create", "show", "edit", "update", "delete")


def resource(
    path: str,
    *,
    to: Callable,
    only: Iterable[str] = ACTIONS,
    ignore: Optional[Iterable[str]] = None,
    singular: bool = False,
    **kwargs: Dict[str, Any],
) -> List[Route]:
    """Shortcut to return a list of REST routes for a resource.

    ## Group resource

    Example: `resource("photos", "Photo")`

    HTTP     PATH                METHOD   USED FOR
    -------- ------------------- -------- -------------------------------
    GET      /photos             index    a list of all photos
    GET      /photos/new         new      form for creating a new photo
    POST     /photos             create   create a new photo
    GET      /photos/:uid        show     show a specific photo
    GET      /photos/:uid/edit   edit     form for editing a specific photo
    PATCH    /photos/:uid        update   update a specific photo
    PUT      /photos/:uid        update   replace a specific photo
    DELETE   /photos/:uid        delete   delete a specific photo

    Note that both PATCH and PUT are routed to the `update` method.


    ## Singular resource

    Sometimes, you have a resource that clients always look up without referencing an ID.
    In this case, you can use `singular=True` to build a set of REST routes without `:uid`.

    Example: `resource("profile", "Profile", singular=True)`

    HTTP     PATH                METHOD   USED FOR
    -------- ------------------- -------- -------------------------------
    GET      /profile/new        new      form for creating the profile
    POST     /profile            create   create the profile
    GET      /profile            show     show the profile
    GET      /profile/edit       edit     form for editing the profile
    PATCH    /profile            update   update the profile
    PUT      /profile            update   replace the profile
    DELETE   /profile            delete   delete the profile


    In both secenarios, we validate the arguments first so we can show errors about what the user has
    typed instead of being about dynamically generated routes.
    """
    res = Route("resource", path, to=to, **kwargs)

    ignore = ignore or []
    _actions = [
        action for action in only
        if (action in ACTIONS) and (action not in ignore)
    ]
    assert _actions, "None of the actions are valid."
    return _expand_routes(res, _actions, SINGLE_ROUTES if singular else GROUP_ROUTES)


def _expand_routes(res, actions, data):
    routes = []
    for method, path, action in data:
        if action not in actions:
            continue
        route = _expand_route(res, method, path, action)
        routes.append(route)
    return routes


def _expand_route(res, method, path, action):
    base_path = "/" + res.path.lstrip("/")
    route = Route(
        method,
        base_path.rstrip("/") + path,
        to=_expand_to(res.to, action),
        defaults=res.defaults,
    )
    route.compile_path()
    route.host = res.host
    return route


def _expand_to(to, action):
    if callable(to):
        return getattr(to, action)
    return to + "." + action
