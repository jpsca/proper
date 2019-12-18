"""
## proper.plugs.session

"""
from ..support import Dot, BadSignature


__all__ = ("session", )


def session(req, resp, app):
    if resp.dispatched:
        if session_was_updated(req):
            update_session_cookie(resp, app)
    else:
        fetch_session(req, resp, app)


def fetch_session(req, resp, app):
    """Get the session data from the cookie and puts into the request and response."""
    session = Dot(get_session(req, app))
    req._Request__original_session = session.copy()
    req._Request__session = session
    resp._Response__session = session


def get_session(req, app):
    serializer = app.get_serializer()
    cookie_value = req.cookies.get(app.config.session.cookie_name)
    if cookie_value is None:
        return {}
    try:
        return serializer.loads(cookie_value, max_age=app.config.session.lifetime)
    except BadSignature:
        return {}


def session_was_updated(req):
    return req.original_session != req.session


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
