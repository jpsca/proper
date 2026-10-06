"""Pub/sub backends for WebSocket channels.

Manages the mapping of stream names to subscribed Channel instances.
When a message is broadcast to a stream, all channels subscribed to
that stream receive it.

`Cable` is the in-process backend: enough for one worker process, or for any
number of worker threads sharing the process. When the WebSockets live in their
own process (`CABLE_PORT`), broadcasts made anywhere else are forwarded to it
over the loopback, signed with the app's secret keys. `WseCable` (`wse.py`)
and `RedisCable` (`redis_cable.py`) build on it.
"""
import http.client
import threading
import typing as t
from contextlib import contextmanager
from urllib.parse import urlsplit

from ..helpers import jsonplus, logger


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from ..core.app_ws import Connection
    from .channel import Channel


__all__ = ("Cable", "CABLE_SALT", "origin_allowed", "allowed_origins")

# Salt of the signature on broadcasts forwarded to the cable process.
CABLE_SALT = "cable-broadcast"
# How long such a broadcast stays valid, in seconds. Loopback is instant;
# this only bounds a replay.
FORWARD_MAX_AGE = 30
FORWARD_TIMEOUT = 2.0


def origin_allowed(origin: str | None, host: str, config: t.Any) -> bool:
    """Whether a WebSocket handshake may go on, judging by its `Origin`.

    Browsers send the cookies of a site with any WebSocket to it, even one a
    page of another site opens, so the server checks where the page is.
    Allowed: no `Origin` (not a browser), an origin in
    `CABLE_ALLOWED_ORIGINS`, one whose host is the `Host` of the handshake
    or the app's `HOST`, and, in `DEBUG`, any port of the handshake's host
    name (the page and the cable listen on different ports there).
    """
    if not origin:
        return True
    origin = origin.strip().rstrip("/").lower()
    listed = {o.rstrip("/").lower() for o in config.get("CABLE_ALLOWED_ORIGINS") or ()}
    if origin in listed:
        return True
    parts = urlsplit(origin)
    host = (host or "").lower()
    if parts.netloc and parts.netloc in (host, str(config.get("HOST") or "").lower()):
        return True
    return bool(
        config.get("DEBUG") and parts.hostname
        and parts.hostname == urlsplit(f"//{host}").hostname
    )


def allowed_origins(config: t.Any) -> list[str]:
    """The origins of `origin_allowed` as a fixed list, for a server that
    allows the handshake's own `Host` by itself and the rest from a list
    (wse-server): `CABLE_ALLOWED_ORIGINS`, the app's `HOST` over http and
    https, and in `DEBUG` localhost and 127.0.0.1 on the app's `PORT`."""
    origins = list(config.get("CABLE_ALLOWED_ORIGINS") or ())
    host = config.get("HOST")
    if host:
        origins += [f"http://{host}", f"https://{host}"]
    if config.get("DEBUG"):
        port = config.get("PORT") or 2300
        origins += [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
    return list(dict.fromkeys(origins))


class Cable:
    def __init__(self) -> None:
        self._streams: dict[str, set["Channel"]] = {}
        # Channels subscribe and unsubscribe from the worker threads their
        # code runs in, while broadcasts are delivered from other threads or
        # from the event loop. Every read and write of `_streams` is guarded,
        # or a stream emptied by one thread can be deleted out from under a
        # subscription another thread just made. Re-entrant because
        # `unsubscribe_all` works through `unsubscribe`.
        self._lock = threading.RLock()
        # Set by `forward_to`: where broadcasts go when this process has no
        # WebSockets of its own.
        self._forward_url: str | None = None
        self._sign: "Callable[[t.Any], str] | None" = None
        # `start()` is what the WebSocket server calls; a process that never
        # does has no subscribers and forwards instead.
        self._started = False
        # The open connections of each user, for `disconnect()`.
        self._connections: dict[t.Any, set["Connection"]] = {}
        # Per thread: the connection to the cable process, kept open between
        # broadcasts, and the broadcasts of an open `batch()`.
        self._local = threading.local()

    @property
    def streams(self) -> dict[str, int]:
        """Return a dict of stream names to listener counts (for debugging)."""
        with self._lock:
            return {
                name: len(channels) for name, channels in self._streams.items()
            }

    def subscribe(self, stream_name: str, channel: "Channel") -> None:
        """Register a channel to receive broadcasts on a stream."""
        with self._lock:
            self._streams.setdefault(stream_name, set()).add(channel)
        logger.debug(
            "[cable] %s subscribed to %s", channel.channel_name, stream_name,
        )

    def unsubscribe(self, stream_name: str, channel: "Channel") -> None:
        """Remove a channel from a stream."""
        with self._lock:
            listeners = self._streams.get(stream_name)
            if not listeners:
                return
            listeners.discard(channel)
            if not listeners:
                del self._streams[stream_name]

    def unsubscribe_all(self, channel: "Channel") -> None:
        """Remove a channel from all streams it is subscribed to: the ones it
        knows about, not every stream of the process."""
        with self._lock:
            for stream_name in list(getattr(channel, "_streams", None) or self._streams):
                self.unsubscribe(stream_name, channel)

    def forward_to(self, url: str, sign: "Callable[[t.Any], str]") -> None:
        """Send the broadcasts of any process that is not serving the
        WebSockets to `url`, the cable process's `CABLE_PATH`, signed with
        `sign`."""
        self._forward_url = url
        self._sign = sign

    @property
    def _forwarding(self) -> bool:
        return bool(self._forward_url) and not self._started

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Send data to all channels subscribed to a stream."""
        if not self._forwarding:
            self._deliver_local(stream_name, data)
            return
        batch = getattr(self._local, "batch", None)
        if batch is not None:
            batch.append({"stream": stream_name, "data": data})
        else:
            self._forward({"stream": stream_name, "data": data})

    @contextmanager
    def batch(self):
        """Send the broadcasts made inside together, when they go to the
        cable process: one request instead of one per broadcast.

        ```python
        with app.cable.batch():
            app.cable.broadcast(f"room:{room.id}", html)
            for user_id in member_ids:
                app.cable.broadcast(f"user:{user_id}:unreads", {"roomId": room.id})
        ```
        """
        if getattr(self._local, "batch", None) is not None:
            yield  # nested: the outer one sends them
            return
        self._local.batch = items = []
        try:
            yield
        finally:
            self._local.batch = None
            if items:
                self._forward(items[0] if len(items) == 1 else {"batch": items})

    def disconnect(self, *, user_id: t.Any) -> None:
        """Close the open connections of a user. Their clients reconnect,
        and subscribe again, so channels authorized at subscription time are
        authorized again: use it after revoking access."""
        if self._forwarding:
            self._forward({"disconnect": {"user_id": user_id}})
        else:
            self._disconnect_local({"user_id": user_id})

    def _disconnect_local(self, who: dict) -> None:
        with self._lock:
            connections = list(self._connections.get(who.get("user_id"), ()))
        for connection in connections:
            connection.close_threadsafe()

    def _register(self, connection: "Connection") -> None:
        with self._lock:
            self._connections.setdefault(connection.user_id, set()).add(connection)

    def _unregister(self, connection: "Connection") -> None:
        if connection.user_id is None:
            return
        with self._lock:
            connections = self._connections.get(connection.user_id)
            if connections is not None:
                connections.discard(connection)
                if not connections:
                    del self._connections[connection.user_id]

    def _forward(self, payload: dict) -> None:
        """POST a broadcast to the cable process, on a connection kept open
        between broadcasts (one per thread). A cable that is down loses the
        message and logs it; the page that broadcast still renders."""
        assert self._forward_url and self._sign
        body = self._sign(payload).encode()
        url = urlsplit(self._forward_url)
        for attempt in (1, 2):
            conn = getattr(self._local, "conn", None)
            if conn is None:
                conn = self._local.conn = http.client.HTTPConnection(
                    url.hostname or "127.0.0.1", url.port, timeout=FORWARD_TIMEOUT
                )
            try:
                conn.request(
                    "POST", url.path, body=body,
                    headers={"Content-Type": "text/plain"},
                )
                response = conn.getresponse()
                response.read()
                status = response.status
                break
            except (OSError, http.client.HTTPException) as error:
                # A connection the cable process closed since the last
                # broadcast fails on reuse: try once more on a new one.
                conn.close()
                self._local.conn = None
                if attempt == 2:
                    logger.warning(
                        "⚠️ [cable] could not reach the cable process at %s: %s",
                        self._forward_url, error,
                    )
                    return
        if status != 204:
            logger.warning(
                "⚠️ [cable] the cable process at %s refused a broadcast: HTTP %s",
                self._forward_url, status,
            )

    def receive_forwarded(self, token: str, loads: "Callable[..., t.Any]") -> bool:
        """Act on what `_forward` sent from another process: a token signed
        with the app's keys (`loads` is `app.loads`), carrying a broadcast
        (`stream` and `data`), several (`batch`), or the user whose
        connections to close (`disconnect`). Return whether it was valid."""
        payload = loads(token, salt=CABLE_SALT, max_age=FORWARD_MAX_AGE)
        if not isinstance(payload, dict) or not (
            "stream" in payload or "batch" in payload or "disconnect" in payload
        ):
            logger.warning("⚠️ [cable] refused a broadcast with a bad signature")
            return False
        if "stream" in payload:
            self._deliver_local(payload["stream"], payload.get("data"))
        for item in payload.get("batch") or ():
            self._deliver_local(item["stream"], item.get("data"))
        if "disconnect" in payload:
            self._disconnect_local(payload["disconnect"])
        return True

    def _deliver_local(self, stream_name: str, data: t.Any) -> None:
        """Deliver data to all local channels subscribed to a stream.

        The data is encoded as JSON once, and each distinct subscription
        (channel and params) gets one frame, shared by all of its
        subscribers. A broadcast doesn't go through `Channel.send()`: every
        subscriber gets the same data, as with any other cable.
        """
        with self._lock:
            subscribed = self._streams.get(stream_name)
            if not subscribed:
                return
            # Take a copy and let go of the lock: sending reaches into
            # channel code, which must never run while the cable is held.
            listeners = list(subscribed)
        logger.debug(
            "[cable] broadcasting to %s (%d listeners)",
            stream_name, len(listeners),
        )
        encoded = None
        messages: dict[str, t.Any] = {}
        for channel in listeners:
            try:
                if encoded is None:
                    encoded = jsonplus.dumps(data)
                prefix = channel._frame_prefix
                message = messages.get(prefix)
                if message is None:
                    message = messages[prefix] = channel._message(data, encoded)
                channel._send(message)
            except Exception:
                logger.exception(
                    "[cable] error sending to %s", channel.channel_name,
                )

    async def start(self) -> None:
        self._started = True
        # no-op for in-process cable.
        ...

    async def stop(self) -> None:
        # no-op for in-process cable.
        ...
