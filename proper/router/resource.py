import re
from typing import TYPE_CHECKING

from ..constants import GET, POST, PUT, DELETE, PATCH
from .route import Route

if TYPE_CHECKING:
    from typing import Callable, Iterable, List, Optional, Union, Tuple
    StrOrIter = Union[Iterable[str], str]


__all__ = ("resource",)

ACTION_INDEX = "index"
ACTION_NEW = "new"
ACTION_CREATE = "create"
ACTION_SHOW = "show"
ACTION_EDIT = "edit"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"

GROUP_ROUTES = (
    (GET, "/", ACTION_INDEX),
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/:pk", ACTION_SHOW),
    (GET, "/:pk/edit", ACTION_EDIT),
    (PATCH, "/:pk", ACTION_UPDATE),
    (PUT, "/:pk", ACTION_UPDATE),
    (DELETE, "/:pk", ACTION_DELETE),
)
SINGLE_ROUTES = (
    (GET, "/new", ACTION_NEW),
    (POST, "/", ACTION_CREATE),
    (GET, "/", ACTION_SHOW),
    (GET, "/edit", ACTION_EDIT),
    (PATCH, "/", ACTION_UPDATE),
    (PUT, "/", ACTION_UPDATE),
    (DELETE, "/", ACTION_DELETE),
)
ACTIONS = (
    ACTION_INDEX,
    ACTION_NEW,
    ACTION_CREATE,
    ACTION_SHOW,
    ACTION_EDIT,
    ACTION_UPDATE,
    ACTION_DELETE,
)
RX_COMMA = re.compile(r",\s*")


def resource(
    path: str,
    *,
    to: "Callable",
    only: "StrOrIter" = ACTIONS,
    exclude: "Optional[StrOrIter]" = None,
    singular=False,
    **kwargs
) -> "List[Route]":
    """Shortcut to return a list of REST routes for a resource.

    You can define a resource that uses only some of the actions
    with `only`, or one that uses all excluding some with `exclude`.

    ## Group resource

    Example: `resource("photos", "Photo")`

    HTTP     PATH                ACTION   USED FOR
    -------- ------------------- -------- -------------------------------
    GET      /photos             index    a list of all photos
    GET      /photos/new         new      form for creating a new photo
    POST     /photos             create   create a new photo
    GET      /photos/:pk        show     show a specific photo
    GET      /photos/:pk/edit   edit     form for editing a specific photo
    PATCH    /photos/:pk        update   update a specific photo
    PUT      /photos/:pk        update   replace a specific photo
    DELETE   /photos/:pk        delete   delete a specific photo

    Note that both PATCH and PUT are routed to the `update` method.


    ## Singular resource

    Sometimes, you have a resource that clients always look up without referencing an ID.
    In this case, you can use `singular=True` to build a set of REST routes without `:pk`.

    Example: `resource("profile", "Profile", singular=True)`

    HTTP     PATH                ACTION   USED FOR
    -------- ------------------- -------- -------------------------------
    GET      /profile/new        new      form for creating the profile
    POST     /profile            create   create the profile
    GET      /profile            show     show the profile
    GET      /profile/edit       edit     form for editing the profile
    PATCH    /profile            update   update the profile
    PUT      /profile            update   replace the profile
    DELETE   /profile            delete   delete the profile


    In both scenarios, we validate the arguments first so we can show errors about what the user has
    typed instead of being about dynamically generated routes.


    ## Undelete support

    If `undelete` is `True`, an undelete will be added as well.

    """
    res = Route("resource", path, to=to, **kwargs)

    only = _to_list(only)
    exclude = _to_list(exclude)

    _actions = [
        action for action in only if (action in ACTIONS) and (action not in exclude)
    ]
    assert _actions, "None of the actions are valid."
    routes = _expand_routes(res, _actions, SINGLE_ROUTES if singular else GROUP_ROUTES)
    return routes


def _to_list(iterable: "Iterable") -> "Iterable":
    iterable = iterable or []
    if isinstance(iterable, str):
        return RX_COMMA.split(iterable.strip())
    return iterable


def _expand_routes(res: Route, actions: "List[str]", data: "Tuple") -> "List[Route]":
    routes = []
    for method, path, action in data:
        if action not in actions:
            continue
        route = _expand_route(res, method, path, action)
        routes.append(route)
    return routes


def _expand_route(res: Route, method: str, path: str, action: str):
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


def _expand_to(to: "Union[Callable, str]", action: str) -> str:
    if callable(to):
        return getattr(to, action)
    return to + "." + action
