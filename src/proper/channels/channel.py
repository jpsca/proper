"""A base channel class for WebSocket communication.

Channels are the WebSocket equivalent of Controllers. Users create
subclasses with lifecycle methods (`subscribed`, `unsubscribed`) and
custom action methods that clients can invoke.

All channels are multiplexed over a single WebSocket endpoint.
"""
import typing as t

from ..constants import AUTH_COOKIE_NAME, AUTH_COOKIE_SALT
from ..core.request import Request
from ..global_context import current
from ..helpers import logger
from ..types import TScope


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..app import App
    from ..models import ProperModel


class Channel:
    # The app's session model, used to resume the connection's session from
    # its signed cookie. `None` (the default) keeps the connection anonymous.
    Session: "type[ProperModel] | None" = None
    auth_cookie_name: str = AUTH_COOKIE_NAME
    auth_cookie_salt: str = AUTH_COOKIE_SALT

    def __init__(
        self,
        app: "App",
        params: dict[str, t.Any],
        *,
        scope: TScope | None = None,
        _send: "Callable[[dict], t.Any]",
    ) -> None:
        """`scope` is the ASGI scope of the WebSocket connection. It carries
        the connection's headers and cookies. It is `None` only when a channel
        is constructed directly (for example, in a unit test)."""
        self.app = app
        self.params = params
        self.scope = scope
        self._send = _send
        self._streams: set[str] = set()
        self._rejected = False
        self._request: Request | None = None

    @property
    def channel_name(self) -> str:
        return type(self).__name__

    @property
    def request(self) -> Request:
        """The connection's request, for reading headers and cookies (for
        example, a signed auth cookie). Built lazily from the ASGI scope:

        ```python
        token = self.request.get_signed_cookie("_auth", salt="auth cookie")
        ```
        """
        if self._request is None:
            scope = self.scope
            if scope is not None and "method" not in scope:
                # A WebSocket handshake is an HTTP GET upgrade; the ASGI
                # WebSocket scope omits "method", which the request needs.
                scope = {**scope, "method": "GET"}
            self._request = Request(scope or {})
        return self._request

    @property
    def authenticated(self) -> bool:
        """`True` when this connection has a logged-in user, resolved from the
        connection's signed session cookie before each dispatch."""
        return current.user is not None

    def subscribed(self) -> None:
        """Called when a client subscribes to this channel.
        Override to set up streams and perform authorization."""

    def unsubscribed(self) -> None:
        """Called when a client unsubscribes or disconnects.
        Override to perform cleanup."""

    def stream_from(self, stream_name: str) -> None:
        """Subscribe this connection to a named broadcast stream."""
        self._streams.add(stream_name)
        self.app.cable.subscribe(stream_name, self)

    def stop_stream_from(self, stream_name: str) -> None:
        """Unsubscribe this connection from a named broadcast stream."""
        self._streams.discard(stream_name)
        self.app.cable.unsubscribe(stream_name, self)

    def stop_all_streams(self) -> None:
        """Unsubscribe this connection from all streams."""
        self.app.cable.unsubscribe_all(self)
        self._streams.clear()

    def send(self, data: t.Any) -> None:
        """Send data directly to this connection."""
        self._send({
            "type": "message",
            "channel": self.channel_name,
            "params": self.params,
            "data": data,
        })

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Broadcast data to all subscribers of a stream."""
        self.app.cable.broadcast(stream_name, data)

    def reject(self) -> None:
        """Reject the subscription. Call this in `subscribed()` to
        deny access."""
        self._rejected = True

    def _resume_session(self) -> "ProperModel | None":
        """Resolve the connection's session from its signed cookie and expose
        it as `current.auth_session` / `current.user`. A no-op when no
        `Session` model is set (the connection stays anonymous)."""
        if session := self._find_session_by_cookie():
            session.touch()  # type: ignore
            current.auth_session = session
            current.user = session.user  # type: ignore
            return session
        return None

    def _find_session_by_cookie(self) -> "ProperModel | None":
        if self.Session is None:
            return None
        token = self.request.get_signed_cookie(
            self.auth_cookie_name,
            salt=self.auth_cookie_salt,
        )
        if token:
            return self.Session.find_by_token(token)  # type: ignore
        return None

    def _dispatch(self, action_name: str, data: dict | None = None) -> None:
        self._resume_session()
        c_name = type(self).__name__
        logger.debug("[%s] dispatching: %s", c_name, action_name)
        method = getattr(self, action_name)
        if data is not None:
            method(data)
        else:
            method()
