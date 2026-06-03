import typing as t

from .constants import (
    DELETE,
    FLASHES_SESSION_KEY,
    GET,
    HEAD,
    OPTIONS,
    PATCH,
    POST,
    PUT,
    QUERY,
)
from .controller import Controller
from .helpers import DotDict, import_string, logger


if t.TYPE_CHECKING:
    from .core.request import Request
    from .core.response import Response


__all__ = (
    "copy_session",
    "head_to_get",
    "method_override",
    "match",
    "redirect",
    "dispatch",
    "strip_body_if_head",
    "update_session_cookie",
)

TController = type[Controller]
LOCAL_HOSTS = ("localhost", "0.0.0.0", "127.0.0.1", "::", "::1")


def copy_session(request: "Request", response: "Response"):
    """Get the session data from the cookie and puts into the request
    and response.
    """
    if request.method in (HEAD, OPTIONS):
        return
    session = _find_session_by_cookie(request)
    request.session = session
    response.session = session.copy()
    if FLASHES_SESSION_KEY in response.session:
        del response.session[FLASHES_SESSION_KEY]


def _find_session_by_cookie(request: "Request") -> DotDict:
    session = request.get_signed_cookie(
        "_session", salt="session", max_age=request.app.config.SESSION_COOKIE_LIFETIME
    )
    logger.debug(">>> %s", session or "")
    return DotDict(session or {})


def head_to_get(request: "Request", _response) -> None:
    """Transform a HEAD request to a fake GET request."""
    if request.request_method == HEAD:
        request.method = GET


def method_override(request: "Request", _response) -> None:
    """Overrides the request's `POST` method with the method defined in
    the `X-HTTP-Method-Override` header or the `_method` parameter in the
    path or in the request body.

    The `POST` method can be overridden only by these HTTP methods:
    * `PUT`
    * `PATCH`
    * `DELETE`
    * `QUERY`

    """
    if request.method != POST:
        return

    new_method = request.headers.get("x-http-method-override")
    if not new_method:
        new_method = request.query.get("_method") or request.form.get("_method")

    new_method = (new_method or "").upper()
    if new_method not in (PUT, PATCH, DELETE, QUERY):
        return

    request.method = new_method


def match(request: "Request", _response) -> "Response | None":
    """Match the request url to a route."""
    host: str | None = request.host
    if host in LOCAL_HOSTS:
        host = None
    router = request.app.router
    route, params = router.match(request.method, request.path, host)
    request.matched_route = route
    request.matched_params = params


def redirect(request: "Request", response: "Response") -> "Response | None":
    """If a matched route is a redirect sets the header and response body
    for that redirect to happen and stop further process of the response.
    """
    route = request.matched_route
    if not route:
        return

    if route.redirect:
        params = request.matched_params or {}
        response.redirect_to(
            route.redirect.format(**params),
            status=route.redirect_status,
        )
        return response


def dispatch(request: "Request", response: "Response") -> "Response | None":
    route = request.matched_route
    assert route
    assert route.to
    cls_name, action_name = route.to.__qualname__.rsplit(".", 1)
    request.matched_action = action_name
    module = import_string(route.to.__module__)
    Controller: TController = getattr(module, cls_name)

    # We instantiate the view class so we can have an independent
    # container for this request.
    co = Controller(request, response)
    co._dispatch(action_name)


def strip_body_if_head(request: "Request", response: "Response") -> None:
    """Strip the response body if the method was HEAD."""
    if request.request_method == HEAD:
        response.body = ""


def update_session_cookie(request: "Request", response: "Response") -> None:
    """Update the session cookie if the session was modified."""
    if request.method in (HEAD, OPTIONS):
        return
    if response.session == request.session:
        return
    if response.session:
        _set_new_session_cookie(request, response)
    else:
        response.unset_cookie("_session")


def _set_new_session_cookie(request: "Request", response: "Response") -> None:
    config = request.app.config
    response.set_signed_cookie(
        "_session",
        dict(response.session),
        salt="session",
        max_age=int(config.SESSION_COOKIE_LIFETIME)
        if config.SESSION_COOKIE_LIFETIME
        else None,
        httponly=config.SESSION_COOKIE_HTTPONLY,
        domain=config.SESSION_COOKIE_DOMAIN,
        path=config.SESSION_COOKIE_PATH or "/",
        secure=request.is_secure,
        samesite=config.SESSION_COOKIE_SAMESITE,
    )
