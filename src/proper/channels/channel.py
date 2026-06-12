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
    # The app's session model, used to authenticate the connection from its
    # signed cookie at subscription time. `None` (the default) keeps the
    # connection anonymous.
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
        self.user_id: t.Any = None
        self._send = _send
        self._streams: set[str] = set()
        self._rejected = False
        self._request: Request | None = None

    @property
    def channel_name(self) -> str:
        return type(self).__name__

    @property
    def authenticated(self) -> bool:
        """`True` when this connection resolved a logged-in user from its
        signed session cookie at subscription time."""
        return self.user_id is not None

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

    def find_user(self, user_id: t.Any) -> "ProperModel | None":
        """Load the connection's user by id. Called before every dispatch
        after `subscribed()` to refresh `current.user` from the database.
        Channels with a `Session` model must implement it (the channels
        addon's `AppChannel` does it for you)."""
        raise NotImplementedError(
            f"{self.channel_name} sets a `Session` model but does not"
            " implement `find_user()`. Implement it to load the user by id"
            " (the channels addon's `AppChannel` does it for you)."
        )

    def _authenticate(self) -> None:
        """Resolve the connection's session from its signed cookie — once, at
        subscription time. Stores the user's id on the instance and exposes
        `current.auth_session` / `current.user` for `subscribed()`. A no-op
        when no `Session` model is set (the connection stays anonymous)."""
        if session := self._find_session_by_cookie():
            session.touch()  # type: ignore
            self.user_id = session.user_id  # type: ignore
            current.auth_session = session
            current.user = session.user  # type: ignore

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

    def _set_current_user(self) -> None:
        """Refresh `current.user` from the database using the id stored at
        subscription time. The session itself is not re-read: it is only
        available, as `current.auth_session`, inside `subscribed()`."""
        if self.user_id is not None:
            current.user = self.find_user(self.user_id)
        else:
            current.user = None
        current.auth_session = None

    def _dispatch(self, action_name: str, data: dict | None = None) -> None:
        if action_name == "subscribed":
            self._authenticate()
        else:
            self._set_current_user()
        c_name = type(self).__name__
        logger.debug("[%s] dispatching: %s", c_name, action_name)
        method = getattr(self, action_name)
        if data is not None:
            method(data)
        else:
            method()
