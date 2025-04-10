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
        app = co.app
        request = co.request
        response = co.response
        session = self._get_session(app, request)
        request.session = session
        response.session = session.copy()
        response.session.pop(FLASHES_SESSION_KEY, None)

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
            logger.debug(">>> %", session)
            return DotDict(session)
        except BadSignature:
            logger.debug(">>> BAD SESSION %", cookie)
            return DotDict()


class UpdateSessionCookie:
    def __call__(self, co: "Controller") -> None:
        """Update the session cookie if its needed."""
        app = co.app
        request = co.request
        response = co.response
        if response.session != request.session:
            self._update_session_cookie(app, response)

    # Private

    def _update_session_cookie(self, app: "App", response: "Response") -> None:
        """Update the session cookie if its needed."""
        config = app.config
        # If the session was modified to be empty, remove the cookie.
        if not response.session:
            response.unset_cookie(
                config.SESSION_COOKIE_NAME,
                path=config.SESSION_COOKIE_PATH or "/",
                domain=config.SESSION_COOKIE_DOMAIN,
            )
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
            secure=config.SESSION_COOKIE_SECURE,
            samesite=config.SESSION_COOKIE_SAMESITE,
        )
