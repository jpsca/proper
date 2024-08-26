import typing as t

from itsdangerous import BadSignature

from proper.constants import FLASHES_SESSION_KEY
from proper.helpers import DotDict


if t.TYPE_CHECKING:
    from proper.core import App
    from proper.request import Request
    from proper.response import Response
    from proper.view import View


__all__ = ("Session", "SESSION_SALT")


SESSION_SALT = "session"


class Session:
    def before(self, view: "View") -> None:
        """Get the session data from the cookie and puts into the request
        and response.
        """
        app = view.app
        request = view.request
        response = view.response
        session = self._get_session(app, request)
        request.session = session
        response.session = session.copy()
        response.session.pop(FLASHES_SESSION_KEY, None)

    def after(self, view: "View") -> None:
        """Update the session cookie if its needed."""
        app = view.app
        request = view.request
        response = view.response
        if response.session != request.session:
            self._update_session_cookie(app, response)

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
            print(">>>", session)
            return DotDict(session)
        except BadSignature:
            print(">>>", "BAD SESSION", cookie)
            return DotDict()

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

        print(">>>", "SET SESSION", dict(response.session))
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
