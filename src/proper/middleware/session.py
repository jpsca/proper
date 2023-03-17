import typing as t
from types import MappingProxyType

from ..constants import FLASHES_SESSION_KEY
from ..helpers import BadSignature, DotDict  # type: ignore

if t.TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = (
    "fetch_session",
    "put_session",
)


def fetch_session(request: "Request", response: "Response", app: "App") -> None:
    """Get the session data from the cookie and puts into the request
    and response.
    """
    session = DotDict(get_session(request, app))
    request._session = MappingProxyType(session)
    response._session = session.copy()
    response._session.pop(FLASHES_SESSION_KEY, None)


def get_session(request: "Request", app: "App") -> dict:
    cookie_value = request.cookies.get(app.config.session.cookie.name)
    if cookie_value is None:
        return {}
    try:
        return app.serializer.loads(cookie_value, max_age=app.config.session.lifetime)
    except BadSignature:
        return {}


def put_session(request: "Request", response: "Response", app: "App") -> None:
    if response.session != request.session:
        update_session_cookie(response, app)


def update_session_cookie(response: "Response", app: "App") -> None:
    """Update the session cookie if its needed."""
    config = app.config.session
    session = response.session

    # If the session was modified to be empty, remove the cookie.
    if not session:
        response.unset_cookie(
            config.cookie.name,
            path=config.cookie.path or "/",
            domain=config.cookie.domain,
        )
        return

    cookie_value = app.serializer.dumps(dict(session))

    response.set_cookie(
        config.cookie.name,
        cookie_value,
        max_age=int(config.lifetime) if config.lifetime else None,
        httponly=config.cookie.httponly,
        domain=config.cookie.domain,
        path=config.cookie.path or "/",
        secure=config.cookie.secure,
        samesite=config.cookie.samesite,
    )
