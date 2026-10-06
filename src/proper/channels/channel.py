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
from ..helpers import jsonplus, logger


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..app import App
    from ..models import ProperModel
    from .cable import WseConnection


class ActionError(Exception):
    """An error an action reports to the client that called it: the reply
    gets `status: "error"` and `{"reason": reason, **data}`.

    ```python
    def speak(self, data):
        if len(data["text"]) > 500:
            raise ActionError("too_long", max=500)
    ```
    """

    def __init__(self, reason: str = "error", **data: t.Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.data = {"reason": reason, **data}


class Message(dict):
    """A message to one subscription (`Channel.send()`), and its JSON."""

    __slots__ = ("json",)

    def __init__(self, prefix: str, channel_name: str, params: dict, data: t.Any, encoded: str):
        super().__init__(type="message", channel=channel_name, params=params, data=data)
        self.json = prefix + encoded + "}"


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
        request: Request | None = None,
        name: str = "",
        _send: "Callable[[t.Any], t.Any]",
        _connection: "WseConnection | None" = None,
    ) -> None:
        """`request` is the WebSocket handshake, which carries the
        connection's headers and cookies. It is `None` only when a channel
        is constructed directly (for example, in a unit test).

        `name` is the one the client subscribed with, under which the router
        registered the channel; the class name if not given."""
        self.app = app
        self.params = params
        self._name = name or type(self).__name__
        self.user_id: t.Any = None
        self._send = _send
        self._streams: set[str] = set()
        self._tracked: set[str] = set()  # the streams it is present in
        self._rejected = False
        self._request = request
        self._connection = _connection
        # Every message to this subscription starts the same way: encoded
        # once, so `send()` only has to encode its data.
        self._frame_prefix = (
            '{"type": "message", "channel": %s, "params": %s, "data": '
            % (jsonplus.dumps(self.channel_name), jsonplus.dumps(params))
        )

    @property
    def channel_name(self) -> str:
        """The name the client subscribed with: the class name, unless the
        channel was registered under another one (`@router.channel("chat")`)."""
        return self._name

    @property
    def authenticated(self) -> bool:
        """`True` when this connection resolved a logged-in user from its
        signed session cookie at subscription time."""
        return self.user_id is not None

    @property
    def request(self) -> Request:
        """The WebSocket handshake as a request: its path and query string
        (`request.query`), its `Cookie`, `Authorization` and
        `X-Forwarded-For` headers, and the client's address
        (`request.remote_ip`). For example:

        ```python
        token = self.request.get_signed_cookie("_auth", salt="auth cookie")
        token = self.request.headers.get("authorization", "").removeprefix("Bearer ")
        ```

        A channel built without one gets an empty request.
        """
        if self._request is None:
            self._request = Request(app=self.app)
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
        """Unsubscribe this connection from a named broadcast stream (and
        leave its presence)."""
        self._streams.discard(stream_name)
        self._tracked.discard(stream_name)
        self.app.cable.unsubscribe(stream_name, self)

    def stop_all_streams(self) -> None:
        """Unsubscribe this connection from all streams (and leave their
        presence)."""
        self.app.cable.unsubscribe_all(self)
        self._streams.clear()
        self._tracked.clear()

    def track(self, stream_name: str, data: dict | None = None, *, key: t.Any = None) -> None:
        """List this connection among those present in a stream it streams
        from (`stream_from()` first), with `data` for the others to see (a
        name, an avatar). The subscribers of the stream get `presence_join`
        the first time the user appears, and `presence_leave` when their
        last connection leaves (on `untrack()`, `stop_stream_from()`,
        `unsubscribe` or disconnect), so three tabs count once.

        Who it is listed as: `key` if given, else the user's id, else a
        random key for the connection (an anonymous visitor with three tabs
        counts three times). The key is decided here, on the server; never
        take it from `params`, or a client can pose as anyone. One per
        connection: a second `track()` with another key is an error.

        ```python
        def subscribed(self):
            stream = f"room_{self.params['room']}"
            self.stream_from(stream)
            self.track(stream, {"name": current.user.name})
        ```
        """
        if stream_name not in self._streams:
            raise ValueError(f"track() needs stream_from({stream_name!r}) first")
        self.app.cable.track(stream_name, data or {}, self, key=key)
        self._tracked.add(stream_name)

    def untrack(self, stream_name: str) -> None:
        """Take this connection off the list of a stream, still streaming
        from it."""
        self._tracked.discard(stream_name)
        self.app.cable.untrack(stream_name, self)

    def update_presence(self, data: dict) -> None:
        """Change the data this connection's user is listed with, in every
        stream they are present in: the others get `presence_update`."""
        self.app.cable.update_presence(self, data)

    def send(self, data: t.Any) -> None:
        """Send data directly to this connection."""
        self._send(self._message(data, jsonplus.dumps(data)))

    def _message(self, data: t.Any, encoded: str) -> Message:
        return Message(self._frame_prefix, self.channel_name, self.params, data, encoded)

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
        """Resolve the connection's session from its signed cookie — once per
        connection, by the first channel that subscribes. The others reuse
        the user's id it found. Exposes `current.user` for `subscribed()`,
        and `current.auth_session` in the `subscribed()` of that first
        channel. A no-op when no `Session` model is set (the connection
        stays anonymous)."""
        if self.Session is None:
            return
        conn = self._connection
        if conn is not None and conn.identified:
            self.user_id = conn.user_id
            current.user = self.find_user(self.user_id) if self.user_id is not None else None
            return
        if session := self.find_session():
            session.touch()  # type: ignore
            self.user_id = session.user_id  # type: ignore
            current.auth_session = session
            current.user = session.user  # type: ignore
        if conn is not None:
            conn.identify(self.user_id)

    def find_session(self) -> "ProperModel | None":
        """Find the connection's session, once per connection, when its
        first channel subscribes. By default, from the signed auth cookie
        of the handshake, as a controller would. Override it to accept a
        token from a client that has no cookies, such as a mobile app:

        ```python
        def find_session(self):
            token = self.request.headers.get("authorization", "").removeprefix("Bearer ")
            return Session.find_by_token(token) if token else super().find_session()
        ```

        Return `None` to leave the connection anonymous. A no-op when no
        `Session` model is set."""
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

    def _dispatch(self, action_name: str, data: dict | None = None) -> t.Any:
        """Run a lifecycle method or an action, with `current.user` set.
        Returns what it returned: the data of the reply, for an action."""
        if action_name == "subscribed":
            self._authenticate()
        else:
            self._set_current_user()
        c_name = type(self).__name__
        logger.debug("[%s] dispatching: %s", c_name, action_name)
        method = getattr(self, action_name)
        if data is not None:
            return method(data)
        return method()
