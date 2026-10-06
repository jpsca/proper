"""The base of the cables, the backends of the WebSocket channels.

`BaseCable` serves no WebSockets: it is what an app without the channels addon
gets (`CABLE = {}`), and a broadcast made with it reaches no one. What it has
is what `Cable` (`cable.py`), the one that serves them, builds on: the
WebSockets are served by one process, and the broadcasts made in any other
one are forwarded to it over the loopback, signed with the app's secret keys.
"""
import http.client
import threading
import typing as t
from contextlib import contextmanager
from urllib.parse import urlsplit

from ..helpers import logger


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from .channel import Channel


__all__ = ("BaseCable", "CABLE_SALT", "origin_allowed", "allowed_origins")

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


class BaseCable:
    def __init__(self) -> None:
        # Guards the state the cables that serve WebSockets keep, which
        # channels change from worker threads.
        self._lock = threading.RLock()
        # Set by `forward_to`: where broadcasts go when this process has no
        # WebSockets of its own.
        self._forward_url: str | None = None
        self._sign: "Callable[[t.Any], str] | None" = None
        # Per thread: the connection to the cable process, kept open between
        # broadcasts, and the broadcasts of an open `batch()`.
        self._local = threading.local()

    @property
    def streams(self) -> dict[str, int]:
        """Stream names and how many subscriptions each has (for debugging).
        None here: no WebSockets, no subscribers."""
        return {}

    def subscribe(self, stream_name: str, channel: "Channel") -> None:
        """Have a channel receive the broadcasts of a stream. A cable that
        serves WebSockets does it; this one has no connections to do it for."""

    def unsubscribe(self, stream_name: str, channel: "Channel") -> None:
        """Stop a channel receiving the broadcasts of a stream."""

    def unsubscribe_all(self, channel: "Channel") -> None:
        """Stop a channel receiving the broadcasts of every stream it
        subscribed to."""
        for stream_name in list(getattr(channel, "_streams", ())):
            self.unsubscribe(stream_name, channel)

    # Presence: who is in a stream. None here, there are no connections.

    def track(self, stream_name: str, data: dict, channel: "Channel", key: t.Any = None) -> None:
        """List the channel's connection among those present in a stream."""

    def untrack(self, stream_name: str, channel: "Channel") -> None:
        """Take the channel's connection off the list of a stream."""

    def update_presence(self, channel: "Channel", data: dict) -> None:
        """Change the data shown for the channel's connection, in every
        stream it is present in."""

    def presence(self, stream_name: str) -> dict[str, dict]:
        """Who is present in a stream: `{key: {"data": ..., "connections": n}}`."""
        return {}

    def presence_stats(self, stream_name: str) -> dict[str, int]:
        """How many are present in a stream: `{"users": n, "connections": n}`."""
        return {"users": 0, "connections": 0}

    def forward_to(self, url: str, sign: "Callable[[t.Any], str]") -> None:
        """Send the broadcasts of any process that is not serving the
        WebSockets to `url`, the cable process's `CABLE_PATH`, signed with
        `sign`."""
        self._forward_url = url
        self._sign = sign

    @property
    def _forwarding(self) -> bool:
        return bool(self._forward_url)

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
        """Close the connections of a user served here: none."""

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
        """Deliver a broadcast to the subscribers served here: none."""
        logger.debug("[cable] no WebSockets: the broadcast to %s reaches no one", stream_name)
