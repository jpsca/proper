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
    serializer = app.get_serializer()
    cookie_value = req.cookies.get(app.config.session.cookie_name)
    if cookie_value is None:
        return {}
    try:
        return serializer.loads(cookie_value, max_age=app.config.session.lifetime)
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
            config.cookie_name,
            path=config.cookie_path or "/",
            domain=config.cookie_domain,
        )
        return

    serializer = app.get_serializer()
    cookie_value = serializer.dumps(dict(session))

    resp.set_cookie(
        config.cookie_name,
        cookie_value,
        max_age=int(config.lifetime) if config.lifetime else None,
        httponly=config.cookie_httponly,
        domain=config.cookie_domain,
        path=config.cookie_path or "/",
        secure=config.cookie_secure,
        samesite=config.cookie_samesite,
    )
