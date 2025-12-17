import typing as t

from proper.constants import FLASHES_SESSION_KEY, HEAD, OPTIONS
from proper.helpers import DotDict, logger


if t.TYPE_CHECKING:
    from proper import Request, Response
    from ..app import App


__all__ = ("copy_session", "update_session_cookie")

SKIP_FOR_METHODS = (HEAD, OPTIONS)


def copy_session(app: "App", request: "Request", response: "Response"):
    """Get the session data from the cookie and puts into the request
    and response.
    """
    if request.method in SKIP_FOR_METHODS:
        return
    session = _find_session_by_cookie(app, request)
    request.session = session
    response.session = session.copy()
    if FLASHES_SESSION_KEY in response.session:
        del response.session[FLASHES_SESSION_KEY]


def _find_session_by_cookie(app: "App", request: "Request") -> DotDict:
    session = request.get_signed_cookie(
        "_session",
        salt="session",
        max_age=app.config.SESSION_COOKIE_LIFETIME
    )
    logger.debug(">>> %s", session or "")
    return DotDict(session or {})


def update_session_cookie(app: "App", request: "Request", response: "Response") -> None:
    """Update the session cookie if the session was modified."""
    if request.method in SKIP_FOR_METHODS:
        return
    if response.session == request.session:
        return
    if response.session:
        _set_new_session_cookie(app, request, response)
    else:
        response.unset_cookie("_session")


def _set_new_session_cookie(app: "App", request: "Request", response: "Response") -> None:
    config = app.config
    response.set_signed_cookie(
        "_session",
        dict(response.session),
        salt="session",
        max_age=int(config.SESSION_COOKIE_LIFETIME) if config.SESSION_COOKIE_LIFETIME else None,
        httponly=config.SESSION_COOKIE_HTTPONLY,
        domain=config.SESSION_COOKIE_DOMAIN,
        path=config.SESSION_COOKIE_PATH or "/",
        secure=request.is_secure,
        samesite=config.SESSION_COOKIE_SAMESITE,
    )
