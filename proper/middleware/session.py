from ..constants import FLASHES_SESSION_KEY
from ..helpers import BadSignature, Dot, FrozenDict


__all__ = ("fetch_session", "put_session",)


def fetch_session(req, resp, app):
    """Get the session data from the cookie and puts into the request
    and response.
    """
    session = Dot(get_session(req, app))
    req._session = FrozenDict(
        session,
        "req.session",
        error="`req.session` is read-only. Update `resp.session` instead"
    )
    resp._session = session.copy()
    resp._session.pop(FLASHES_SESSION_KEY, None)


def get_session(req, app):
    cookie_value = req.cookies.get(app.config.session.cookie.name)
    if cookie_value is None:
        return {}
    try:
        return app.serializer.loads(cookie_value, max_age=app.config.session.lifetime)
    except BadSignature:
        return {}


def put_session(req, resp, app):
    if resp.session != req.session:
        update_session_cookie(resp, app)


def update_session_cookie(resp, app):
    """Update the session cookie if its needed."""
    config = app.config.session
    session = resp.session

    # If the session was modified to be empty, remove the cookie.
    if not session:
        resp.delete_cookie(
            config.cookie.name,
            path=config.cookie.path or "/",
            domain=config.cookie.domain,
        )
        return

    cookie_value = app.serializer.dumps(dict(session))

    resp.set_cookie(
        config.cookie.name,
        cookie_value,
        max_age=int(config.lifetime) if config.lifetime else None,
        httponly=config.cookie.httponly,
        domain=config.cookie.domain,
        path=config.cookie.path or "/",
        secure=config.cookie.secure,
        samesite=config.cookie.samesite,
    )
