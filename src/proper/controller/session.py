import typing as t

from itsdangerous import BadSignature

from proper.constants import FLASHES_SESSION_KEY
from proper.helpers import DotDict

if t.TYPE_CHECKING:
    from proper import App, Request, Response


__all__ = ("Session", )


class Session:
    app: "App"
    request: "Request"
    response: "Response"

    def __before__(self) -> None:
        self._fetch_session()

    def __after__(self) -> None:
        self._put_session()

    def _fetch_session(self) -> None:
        """Get the session data from the cookie and puts into the request
        and response.
        """
        session = self._get_session()
        self.request._session = session
        self.response._session = session.copy()
        self.response._session.pop(FLASHES_SESSION_KEY, None)

    def _get_session(self) -> DotDict:
        """Get the session data from the cookie."""
        cookie_value = self.request.cookies.get(self.app.config.SESSION_COOKIE_NAME)
        if cookie_value is None:
            return DotDict()
        try:
            session = self.app.serializer.loads(
                cookie_value,
                max_age=self.app.config.SESSION_LIFETIME,
            )  # type: ignore
            return DotDict(session)
        except BadSignature:
            return DotDict()

    def _put_session(self) -> None:
        """Update the session cookie if its needed."""
        if self.response.session != self.request.session:
            self._update_session_cookie()

    def _update_session_cookie(self) -> None:
        """Update the session cookie if its needed."""
        config = self.app.config
        session = self.response.session

        # If the session was modified to be empty, remove the cookie.
        if not session:
            self.response.unset_cookie(
                config.SESSION_COOKIE_NAME,
                path=config.SESSION_COOKIE_PATH or "/",
                domain=config.SESSION_COOKIE_DOMAIN,
            )
            return

        cookie_value = self.app.serializer.dumps(dict(session))
        if isinstance(cookie_value, bytes):
            cookie_value = cookie_value.decode("utf8")

        self.response.set_cookie(
            config.SESSION_COOKIE_NAME,
            cookie_value,
            max_age=int(config.SESSION_LIFETIME) if config.SESSION_LIFETIME else None,
            httponly=config.SESSION_COOKIE_HTTPONLY,
            domain=config.SESSION_COOKIE_DOMAIN,
            path=config.SESSION_COOKIE_PATH or "/",
            secure=config.SESSION_COOKIE_SECURE,
            samesite=config.SESSION_COOKIE_SAMESITE,
        )
