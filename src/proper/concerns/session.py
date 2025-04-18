import typing as t

from itsdangerous import BadSignature

from proper.constants import FLASHES_SESSION_KEY
from proper.helpers import DotDict, logger


if t.TYPE_CHECKING:
    from proper.controller import Controller
    from proper.core.app import App
    from proper.request import Request
    from proper.response import Response


__all__ = ("RestoreSession", "UpdateSessionCookie", "SESSION_SALT")


SESSION_SALT = "session"


class RestoreSession:
    def __call__(self, co: "Controller") -> None:
        """Get the session data from the cookie and puts into the request
        and response.
        """
        session = self._get_session(co.app, co.request)
        co.request.session = session
        co.response.session = session.copy()
        if FLASHES_SESSION_KEY in co.response.session:
            del co.response.session[FLASHES_SESSION_KEY]

    # Private

    def _get_session(self, app: "App", request: "Request") -> DotDict:
        """Get the session data from the cookie."""
        cookie = request.cookies.get(app.config.SESSION_COOKIE_NAME)
        if cookie is None:
            return DotDict()

        try:
            session = request.get_signed_cookie(
                app.config.SESSION_COOKIE_NAME,
                salt=SESSION_SALT,
                max_age=app.config.SESSION_LIFETIME
            )
            logger.debug(">>> %s", session or "")
            return DotDict(session)
        except BadSignature:
            logger.debug(">>> BAD SESSION %s", cookie)
            return DotDict()


class UpdateSessionCookie:
    def __call__(self, co: "Controller") -> None:
        """Update the session cookie if its needed."""
        if co.response.session != co.request.session:
            self._update_session_cookie(co.app, co.request, co.response)

    # Private

    def _update_session_cookie(self, app: "App", request: "Request", response: "Response") -> None:
        """Update the session cookie if its needed."""
        config = app.config
        # If the session was modified to be empty, remove the cookie.
        if not response.session:
            response.unset_cookie(config.SESSION_COOKIE_NAME)
            return

        logger.debug(">>> SET SESSION %s", dict(response.session))
        response.set_signed_cookie(
            config.SESSION_COOKIE_NAME,
            dict(response.session),
            salt=SESSION_SALT,
            max_age=int(config.SESSION_LIFETIME) if config.SESSION_LIFETIME else None,
            httponly=config.SESSION_COOKIE_HTTPONLY,
            domain=config.SESSION_COOKIE_DOMAIN,
            path=config.SESSION_COOKIE_PATH or "/",
            secure=request.is_secure,
            samesite=config.SESSION_COOKIE_SAMESITE,
        )
