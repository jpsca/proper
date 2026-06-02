"""A base channel class for WebSocket communication.

Channels are the WebSocket equivalent of Controllers. Users create
subclasses with lifecycle methods (`subscribed`, `unsubscribed`) and
custom action methods that clients can invoke.

All channels are multiplexed over a single WebSocket endpoint.
"""
import typing as t

from ..helpers import logger


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..app import App


class Channel:
    def __init__(
        self,
        app: "App",
        params: dict[str, t.Any],
        *,
        _send: "Callable[[dict], t.Any]",
    ) -> None:
        self.app = app
        self.params = params
        self._send = _send
        self._streams: set[str] = set()
        self._rejected = False

    @property
    def channel_name(self) -> str:
        return type(self).__name__

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

    def _dispatch(self, action_name: str, data: dict | None = None) -> None:
        c_name = type(self).__name__
        logger.debug("[%s] dispatching: %s", c_name, action_name)
        method = getattr(self, action_name)
        if data is not None:
            method(data)
        else:
            method()
