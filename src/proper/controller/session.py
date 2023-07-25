import typing as t

from itsdangerous import BadSignature

from ..constants import FLASHES_SESSION_KEY
from ..helpers import DotDict

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
        session = DotDict(self._get_session())
        self.request._session = session
        self.response._session = session.copy()
        self.response._session.pop(FLASHES_SESSION_KEY, None)

    def _get_session(self) -> dict:
        """Get the session data from the cookie."""
        cookie_value = self.request.cookies.get(self.app.config.session.cookie.name)
        if cookie_value is None:
            return {}
        try:
            return self.app.serializer.loads(
                cookie_value,
                max_age=self.app.config.session.lifetime,
            )  # type: ignore
        except BadSignature:
            return {}

    def _put_session(self) -> None:
        """Update the session cookie if its needed."""
        if self.response.session != self.request.session:
            self._update_session_cookie()

    def _update_session_cookie(self) -> None:
        """Update the session cookie if its needed."""
        config = self.app.config.session
        session = self.response.session

        # If the session was modified to be empty, remove the cookie.
        if not session:
            self.response.unset_cookie(
                config.cookie.name,
                path=config.cookie.path or "/",
                domain=config.cookie.domain,
            )
            return

        cookie_value = self.app.serializer.dumps(dict(session))
        if isinstance(cookie_value, bytes):
            cookie_value = cookie_value.decode("utf8")

        self.response.set_cookie(
            config.cookie.name,
            cookie_value,
            max_age=int(config.lifetime) if config.lifetime else None,
            httponly=config.cookie.httponly,
            domain=config.cookie.domain,
            path=config.cookie.path or "/",
            secure=config.cookie.secure,
            samesite=config.cookie.samesite,
        )
