"""The cable: the WebSockets of the channels, served by Bearings.

`subscribed()`, the actions and `unsubscribed()` of the channels run in
Python, in Bearings' worker threads, and decide what each connection streams
from. Under them:

- The WebSockets are served by Bearings (`bearings.Server`, the same server
  as the app's HTTP) on `CABLE_PORT`, inside the web process. No second
  process, and a `broadcast()` made by a controller needs no forwarding.
- A stream is a Bearings topic. `stream_from()` subscribes the connection to
  it, and `broadcast()` publishes the encoded frame, which Bearings writes to
  every subscriber without Python: one frame, built once.
- Because a broadcast is the same text for every subscriber, its frame names
  the stream, not the channel and params of each subscription:
  `{"c": "P", "type": "broadcast", "stream": ..., "data": ...}`. The
  confirmation of a subscription lists its streams, so the client routes by
  stream. Messages sent with `send()` keep their channel and params.
- Recovery (the last broadcasts of each stream, for a client that
  reconnects) and presence (who is in each stream) are kept in Python.

```python
CABLE = {"type": "proper.channels.Cable"}   # serves on CABLE_PORT
```

Without the channels addon, `CABLE = {}` is a `BaseCable` (`base.py`): no
WebSockets, and a broadcast reaches no one. On several machines, use
`RedisCable` (`redis_cable.py`).

`proper run` starts the server, in its web process, before it serves the
first request (`start_server()`; call it yourself under another server).
Every other process that loads the app (the copies of `PROCESSES`, a task
worker, a shell) has no WebSockets: its broadcasts and `disconnect()`s are
forwarded to that one, signed with the app's keys, over HTTP on
`127.0.0.1:forward_port` (`CABLE_PORT + 1` unless given).

The cable pings every connection each `CABLE_PING_INTERVAL` seconds
(`{"c": "WSE", "t": "ping"}`), which `cable.js` answers and uses to notice
a dead connection; one that answers no ping for `idle_timeout` seconds (60)
is closed. Handshakes from other sites' pages are refused (see
`origin_allowed`).
"""
import contextvars
import json
import os
import queue
import re
import secrets
import threading
import time
import typing as t
from collections import deque
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bearings import Server, WebSocketHandler

from ..global_context import current
from ..helpers import jsonplus, logger
from .base import CABLE_SALT, BaseCable, allowed_origins
from .channel import ActionError


if t.TYPE_CHECKING:
    from ..app import App
    from .channel import Channel


_DISCONNECT = object()
_BLOCKED_ACTIONS = (
    "subscribed", "unsubscribed",
    "send", "broadcast", "reject",
    "stream_from", "stop_stream_from", "stop_all_streams",
    "track", "untrack", "update_presence",
    "find_user", "find_session",
)


def _broadcast_frame(stream_name: str, data: t.Any) -> str:
    """The frame of a broadcast: the same text for every subscriber."""
    return '{"c": "P", "type": "broadcast", "stream": %s, "data": %s}' % (
        jsonplus.dumps(stream_name), jsonplus.dumps(data)
    )


def _subscription_key(channel_name: str, params: dict) -> str:
    return f"{channel_name}:{sorted(params.items())}"


_EPOCH = re.compile(r"^[0-9a-f]{8}$")


def _client_positions(value: t.Any) -> dict[str, list[tuple[str, int]]]:
    """The positions a `subscribe` command carries, `{stream: [{"e": epoch,
    "o": offset}, ...]}` (or one `{"e", "o"}`), as `{stream: [(epoch,
    offset), ...]}`; the malformed ones left out. The epoch is eight hex
    digits. Several per stream: the server's buffer of a stream gets a new
    epoch when it starts again, and the client may have seen both."""
    positions: dict[str, list[tuple[str, int]]] = {}
    if not isinstance(value, dict):
        return positions
    for stream, given in value.items():
        if not isinstance(stream, str):
            continue
        for pos in given if isinstance(given, list) else [given]:
            if not isinstance(pos, dict):
                continue
            epoch, offset = pos.get("e"), pos.get("o")
            if (
                isinstance(epoch, str) and _EPOCH.match(epoch)
                and isinstance(offset, int) and not isinstance(offset, bool) and offset >= 0
            ):
                positions.setdefault(stream, []).append((epoch, offset))
    return positions


def _position(topic_result: dict) -> dict | None:
    """A stream's position as the client gets it, from what the server returned."""
    if topic_result.get("epoch") is None:
        return None
    return {"e": topic_result["epoch"], "o": topic_result["offset"]}


def _stamp(frame: str, topic: str, epoch: str, offset: int) -> str:
    """Stamp a frame when recovery is on: the topic, the epoch of its
    buffer and the offset of the message, first."""
    return '{"tp": %s, "e": "%s", "o": %d, %s' % (jsonplus.dumps(topic), epoch, offset, frame[1:])


def _handshake_request(app: "App", details: dict) -> t.Any:
    """The handshake as a request, for the channels: its path and query
    string, its `Cookie`, `Authorization` and `X-Forwarded-For` headers, and
    the client's address (`request.remote_ip`). `details` is what
    `BearingsServer.opened()` takes from the handshake, or what a test gives
    `InMemoryServer.connect()`.

    A `remote_addr` that isn't `ip:port` is still the peer, checked against
    `TRUSTED_PROXIES`. Without `remote_addr` (the in-memory server's
    `connect()` without details) the handshake has no peer, and its
    `X-Forwarded-For` is left out: a request without a peer counts as from
    a trusted proxy, which here nothing says it came from, so the client
    could choose its `remote_ip`."""
    path, _, query_string = str(details.get("path") or "/").partition("?")
    remote_addr = str(details.get("remote_addr") or "")
    headers = [
        (name, value)
        for name, value in (
            ("cookie", details.get("cookies")),
            ("authorization", details.get("authorization")),
            ("x-forwarded-for", details.get("forwarded_for") if remote_addr else None),
        )
        if value
    ]
    host, _, port = remote_addr.rpartition(":")
    if host and port.isdigit():
        client = (host.strip("[]"), int(port))
    else:
        client = (remote_addr.strip("[]"), None) if remote_addr else None
    return app.request_cls(
        method="GET", path=path, query_string=query_string, headers=headers,
        client=client, app=app,
    )


class Connection:
    """One WebSocket of the cable, as the channels see it."""

    def __init__(self, cable: "Cable", conn_id: str, details: dict) -> None:
        self.cable = cable
        self.conn_id = conn_id
        self.request = _handshake_request(cable.app, details)
        self.subscriptions: dict[str, "Channel"] = {}
        self.identified = False
        self.user_id: t.Any = None
        # What presence lists the connection as, once it is tracked somewhere
        self.presence_key: str | None = None
        self.closing = False
        # Commands run one at a time, in order, in the worker threads.
        self._commands: deque = deque()
        self._lock = threading.Lock()
        self._running = False

    # The interface `Channel` uses.

    def identify(self, user_id: t.Any) -> None:
        self.identified = True
        self.user_id = user_id
        if user_id is not None:
            self.cable._register(self)

    def presence_identity(self, key: t.Any = None) -> None:
        """Give the connection the key presence lists it as, once: `key`,
        else the user's id, else a random one for the connection."""
        if key is None:
            key = self.user_id if self.user_id is not None else f"anon:{secrets.token_urlsafe(9)}"
        key = str(key)
        if self.presence_key is None:
            self.cable.server.set_connection_user(self.conn_id, key)
            self.presence_key = key
        elif self.presence_key != key:
            raise ValueError(
                f"the connection is already present as {self.presence_key!r}, not {key!r}"
            )

    def close_threadsafe(self, code: int = 1000) -> None:
        self.cable.server.disconnect(self.conn_id)

    def put(self, msg: t.Any) -> None:
        if isinstance(msg, str):
            text = msg
        else:
            text = getattr(msg, "json", None) or jsonplus.dumps(msg)
        try:
            self.cable.server.send(self.conn_id, text)
        except RuntimeError:  # pragma: no cover - a command ending as the server stops
            pass

    put_threadsafe = put

    # Ordering

    def enqueue(self, command: t.Any) -> None:
        with self._lock:
            self._commands.append(command)
            if self._running:
                return
            self._running = True
        self.cable._executor.submit(self._run)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._commands:
                    self._running = False
                    return
                command = self._commands.popleft()
            # Each command in a context of its own: the worker threads run
            # the commands of every connection, and what one sets in
            # `current` (the user, the session) must not reach the next.
            contextvars.Context().run(self._run_one, command)

    def _run_one(self, command: t.Any) -> None:
        current.app = self.cable.app
        try:
            if command is _DISCONNECT:
                self.cable._cleanup(self)
            else:
                self.cable._command(self, command)
        except Exception:
            logger.exception("[cable] error handling a command")


class _ForwardedHandler(BaseHTTPRequestHandler):
    """Takes the broadcasts other processes forward (`BaseCable._forward`),
    and serves the metrics (`GET /metrics`), on the loopback port."""

    protocol_version = "HTTP/1.1"  # the senders keep their connection open
    server: "_ForwardedServer"

    def do_GET(self) -> None:
        if self.path != "/metrics":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = self.server.cable.metrics().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        cable = self.server.cable
        token = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path != cable.app.config.get("CABLE_PATH", "/cable"):
            status = 404
        else:
            valid = cable.receive_forwarded(token.decode("utf-8", "replace"), cable.app.loads)
            status = 204 if valid else 403
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: t.Any) -> None:
        pass  # one line per broadcast would drown the log


class _ForwardedServer(ThreadingHTTPServer):
    daemon_threads = True
    cable: "Cable"


class _InlineExecutor:
    """Runs what it is given right away, in the calling thread."""

    def submit(self, fn: t.Callable[[], None]) -> None:
        fn()


class _Buffer:
    """The recovery buffer of a stream."""

    __slots__ = ("epoch", "offset", "frames", "last", "size")

    def __init__(self, size: int) -> None:
        self.epoch = secrets.token_hex(4)
        self.offset = -1  # of the last message
        self.frames: deque[tuple[int, str]] = deque(maxlen=size)
        self.last = time.monotonic()  # when the last message came
        self.size = 0  # the length of its frames


class _Present:
    """A user present in a stream."""

    __slots__ = ("data", "connections")

    def __init__(self, data: dict) -> None:
        self.data = data
        self.connections: set[t.Any] = set()


class _Streams:
    """What a cable's server keeps in Python: who streams from what, the
    recovery buffers and presence. Writing to the connections is the
    transport's (`_write`, `_fanout`, `_joined`, `_left`): in memory for
    tests (`InMemoryServer`), or Bearings (`BearingsServer`)."""

    def __init__(self, cable: "Cable") -> None:
        self.cable = cable
        # Reentrant: a recovery subscribes and writes under it, so that no
        # broadcast to the stream comes in between.
        self._lock = threading.RLock()
        self._open: set[t.Any] = set()
        self._topics: dict[str, set[t.Any]] = {}
        # Recovery: per stream, the epoch of its buffer, the offset of the
        # last message, and the last `recovery_buffer_size` frames.
        self.recovery_enabled = cable._recovery
        self.buffer_size = cable._recovery_buffer_size
        self.buffer_ttl = cable._recovery_ttl
        self.memory_budget = cable._recovery_memory_budget
        # Ordered by the last broadcast, oldest first: the first to drop
        self._buffers: dict[str, _Buffer] = {}
        self._buffers_size = 0
        self._next_purge = 0.0
        # Presence: a connection's user, and per stream and user, their
        # data and connections.
        self.presence_enabled = cable._presence
        self._users: dict[t.Any, str] = {}
        self._presence: dict[str, dict[str, _Present]] = {}

    # The transport

    def _write(self, conn_id: t.Any, text: str) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _fanout(self, topic: str, text: str) -> None:
        """Write `text` to every connection that streams from `topic`."""
        with self._lock:
            conn_ids = list(self._topics.get(topic, ()))
        for conn_id in conn_ids:
            self._write(conn_id, text)

    def _joined(self, conn_id: t.Any, topic: str) -> None:
        """The connection streams from `topic` now."""

    def _left(self, conn_id: t.Any, topic: str) -> None:
        """The connection no longer streams from `topic`."""

    # What Cable calls

    def send(self, conn_id: t.Any, text: str) -> None:
        if conn_id in self._open:
            self._write(conn_id, text)

    def subscribe_connection(
        self, conn_id: t.Any, topics: list[str], presence_data: dict | None = None
    ) -> None:
        for topic in topics:
            with self._lock:
                conn_ids = self._topics.setdefault(topic, set())
                new = conn_id not in conn_ids
                conn_ids.add(conn_id)
            if new:
                self._joined(conn_id, topic)
        # With presence data, the connection is listed in the topics, as the
        # user `set_connection_user` gave it; one without a user is not.
        user = self._users.get(conn_id) if self.presence_enabled else None
        if presence_data is None or user is None:
            return
        for topic in topics:
            with self._lock:
                members = self._presence.setdefault(topic, {})
                entry = members.get(user)
                first = entry is None
                if entry is None:
                    entry = members[user] = _Present(presence_data)
                entry.connections.add(conn_id)
                data, count = entry.data, len(entry.connections)
            self.cable._presence_changed(
                "join" if first else "connections", topic, user, data, count
            )

    def unsubscribe_connection(self, conn_id: t.Any, topics: list[str]) -> None:
        for topic in topics:
            with self._lock:
                conn_ids = self._topics.get(topic, set())
                was = conn_id in conn_ids
                conn_ids.discard(conn_id)
                if was and not conn_ids:
                    del self._topics[topic]
            if was:
                self._left(conn_id, topic)
        self.untrack_presence(conn_id, topics)

    # Presence (`presence_enabled`)

    def set_connection_user(self, conn_id: t.Any, user_id: str) -> None:
        self._need_presence()
        self._users[conn_id] = user_id

    def untrack_presence(self, conn_id: t.Any, topics: list[str]) -> None:
        self._need_presence()
        for topic in topics:
            with self._lock:
                members = self._presence.get(topic, {})
                changed = []  # (user, data, the connections it has left)
                for user, entry in list(members.items()):
                    if conn_id in entry.connections:
                        entry.connections.discard(conn_id)
                        changed.append((user, entry.data, len(entry.connections)))
                        if not entry.connections:
                            del members[user]
            for user, data, count in changed:
                self.cable._presence_changed(
                    "leave" if not count else "connections", topic, user, data, count
                )

    def update_presence(self, conn_id: t.Any, data: dict) -> None:
        self._need_presence()
        user = self._users.get(conn_id)
        if user is None:
            raise RuntimeError("Failed to update presence data (unknown connection)")
        for topic, members in list(self._presence.items()):
            entry = members.get(user)
            if entry is not None and conn_id in entry.connections:
                entry.data = data
                self.cable._presence_changed(
                    "update", topic, user, data, len(entry.connections)
                )

    def presence(self, topic: str) -> dict:
        with self._lock:
            return {
                user: {"data": entry.data, "connections": len(entry.connections)}
                for user, entry in self._presence.get(topic, {}).items()
            }

    def _need_presence(self) -> None:
        if not self.presence_enabled:
            raise RuntimeError("Presence is not enabled")

    def _presence_frame(self, kind: str, topic: str, user: str, data: dict) -> None:
        """A presence event, to the subscribers of the stream, as
        `cable.js` reads it."""
        self._fanout(topic, jsonplus.dumps({
            "c": "WSE", "t": kind, "p": {"topic": topic, "user_id": user, "data": data},
        }))

    def broadcast_local(self, topic: str, text: str) -> None:
        # Stamped and handed over under the lock: the offsets of a stream
        # reach its subscribers in order.
        with self._lock:
            if self.recovery_enabled:
                self._purge()
                buffer = self._buffers.pop(topic, None)  # to the end: the newest
                if buffer is None:
                    buffer = _Buffer(self.buffer_size)
                self._buffers[topic] = buffer
                buffer.last = time.monotonic()
                buffer.offset += 1
                text = _stamp(text, topic, buffer.epoch, buffer.offset)
                if len(buffer.frames) == buffer.frames.maxlen:  # the oldest goes
                    self._resize(buffer, -len(buffer.frames[0][1]))
                buffer.frames.append((buffer.offset, text))
                self._resize(buffer, len(text))
                self._keep_to_budget(topic)
            self._fanout(topic, text)

    def _purge(self) -> None:
        """Drop the buffers of the streams with no broadcast for `buffer_ttl`
        seconds; a client that comes back to one gets `recovered: false`.
        At most once a second, under the lock."""
        now = time.monotonic()
        if now < self._next_purge:
            return
        self._next_purge = now + 1
        stale = now - self.buffer_ttl
        for topic in [topic for topic, buffer in self._buffers.items() if buffer.last < stale]:
            self._drop_buffer(topic)

    def _resize(self, buffer: _Buffer, change: int) -> None:
        buffer.size += change
        self._buffers_size += change

    def _drop_buffer(self, topic: str) -> None:
        self._buffers_size -= self._buffers.pop(topic).size

    def _keep_to_budget(self, topic: str) -> None:
        """Past `memory_budget`, drop the buffers of the streams whose last
        broadcast is the oldest, but never the one just broadcast to."""
        while self._buffers_size > self.memory_budget:
            oldest = next(iter(self._buffers))
            if oldest == topic:
                return
            self._drop_buffer(oldest)

    def subscribe_with_recovery(
        self, conn_id: t.Any, topics: list[str], recover: bool = False,
        epoch: str | None = None, offset: int | None = None,
    ) -> dict:
        """Subscribe, and with `recover`, write to the connection the frames
        of the topics after `offset` in `epoch`. Returns the position of each
        topic and whether it was recovered."""
        result: dict[str, t.Any] = {"recovered": recover and bool(topics), "topics": {}}
        with self._lock:  # no broadcast between the missed frames and the next
            self.subscribe_connection(conn_id, topics)
            for topic in topics:
                buffer = self._buffers.get(topic)
                recovered = False
                if buffer is None:
                    position: dict[str, t.Any] = {"epoch": None, "offset": 0, "recoverable": False}
                else:
                    frames = list(buffer.frames)
                    position = {"epoch": buffer.epoch, "offset": buffer.offset, "recoverable": True}
                    oldest = frames[0][0]  # a buffer is made with its first frame
                    if (
                        recover and epoch == buffer.epoch and offset is not None
                        and offset >= oldest - 1
                    ):
                        for frame_offset, text in frames:
                            if frame_offset > offset:
                                self.send(conn_id, text)
                        recovered = True
                if not recovered:
                    result["recovered"] = False
                result["topics"][topic] = {**position, "recovered": recovered}
        return result

    def health_snapshot(self) -> dict:
        with self._lock:
            return {
                "connections": len(self._open),
                "recovery_enabled": self.recovery_enabled,
                "recovery_topic_count": len(self._buffers),
                "recovery_bytes": self._buffers_size,
                "presence_enabled": self.presence_enabled,
                "presence_topics": len(self._presence),
            }

    def prometheus_metrics(self) -> str:
        return (
            "# HELP proper_cable_connections WebSockets open\n"
            "# TYPE proper_cable_connections gauge\n"
            f"proper_cable_connections {len(self._open)}\n"
        )

    def _forget(self, conn_id: t.Any) -> bool:
        """The connection ended: out of every stream and presence list.
        False if it had already."""
        with self._lock:
            if conn_id not in self._open:
                return False
            self._open.discard(conn_id)
            for topic, conn_ids in list(self._topics.items()):
                conn_ids.discard(conn_id)
                if not conn_ids:
                    del self._topics[topic]
            tracked = [topic for topic, members in self._presence.items()
                       if any(conn_id in e.connections for e in members.values())]
        if tracked:
            self.untrack_presence(conn_id, tracked)
        self._users.pop(conn_id, None)
        return True


class InMemoryServer(_Streams):
    """The cable's server in memory, for tests (`Cable.serve_in_memory()`).
    A connection is a queue of the text frames written to it; `None` marks
    that the server closed it. The client side (`connect`, `client_send`,
    `client_close`, `frames`) is what `TestClient.websocket()` drives."""

    def __init__(self, cable: "Cable") -> None:
        super().__init__(cable)
        # Kept after a connection closes, so its client can read the rest.
        self._frames: dict[str, "queue.Queue[str | None]"] = {}
        self._count = 0

    # The client side

    def connect(self, details: dict | None = None) -> str:
        """A client connects. `details` is its handshake: `cookies`,
        `authorization`, `path` (with the query string), `remote_addr` and
        `forwarded_for`."""
        with self._lock:
            self._count += 1
            conn_id = f"memory-{self._count}"
            self._frames[conn_id] = queue.Queue()
            self._open.add(conn_id)
        self.cable._handle_event("connect", conn_id, details or {})
        return conn_id

    def client_send(self, conn_id: str, text: str) -> None:
        """A text frame from the client."""
        self.cable._handle_event("raw", conn_id, text)

    def client_close(self, conn_id: str) -> None:
        if self._forget(conn_id):
            self.cable._handle_event("disconnect", conn_id, "")

    def frames(self, conn_id: str) -> "queue.Queue[str | None]":
        return self._frames[conn_id]

    def is_open(self, conn_id: str) -> bool:
        return conn_id in self._open

    # The transport

    def _write(self, conn_id: str, text: str) -> None:
        if conn_id in self._open:
            self._frames[conn_id].put(text)

    def disconnect(self, conn_id: str) -> None:
        """The server closes a connection; the client sees it end."""
        if self._forget(conn_id):
            self._frames[conn_id].put(None)
            self.cable._handle_event("disconnect", conn_id, "")


# What `cable.js` gets every `CABLE_PING_INTERVAL` seconds, and answers.
PING = '{"c": "WSE", "t": "ping", "p": {}}'
PONG = '{"c":"WSE","t":"PONG","p":{}}'
# The topic every connection is subscribed to, for the pings; a stream's
# topic is its name in hex, after an "s" (`_topic`), so it can't be this.
ALL = "all"
# Close code for a connection that fell too far behind (RFC 6455: "try again
# later"): `cable.js` reconnects, and recovers what it missed.
TOO_FAR_BEHIND = 1013


def _topic(stream: str) -> str:
    """Bearings' topic for a stream: any text, as one level without
    Bearings' wildcards."""
    return "s" + stream.encode().hex()


class BearingsServer(_Streams, WebSocketHandler):
    """The cable's server: the WebSockets on Bearings, on `CABLE_PORT`.

    A broadcast is one publish to the stream's topic: Bearings encodes the
    frame once and writes it to every subscriber, on its event loops,
    without Python. The events of each connection come one at a time, in
    order, on Bearings' worker threads, which also run the channels.
    """

    def __init__(self, cable: "Cable", port: int) -> None:
        super().__init__(cable)
        config = cable.app.config
        self.port = port
        self.ping_interval = float(config.get("CABLE_PING_INTERVAL") or 3)
        high_water = int(config.get("CABLE_MAX_PENDING_BYTES") or 4 * 1024 * 1024)
        self.server = Server(
            _no_http,
            host=cable._host,
            port=port,
            loops=cable._loops,
            workers=cable._workers,
            max_connections=cable._max_connections,
            websocket=self,
            ws_path=config.get("CABLE_PATH", "/cable"),
            origins=allowed_origins(config),
            any_port_origin=bool(config.get("DEBUG")),
            # The pings are the application's own (`PING`), which `cable.js`
            # answers; a client that answers none for `idle_timeout` is closed.
            ping_interval=0,
            idle_timeout=cable._idle_timeout,
            send_high_water=high_water,
            close_on_backpressure=True,
            ignore_text=PONG,
        )
        self._stopping = threading.Event()
        self._pinger: threading.Thread | None = None

    def start(self) -> None:
        self.server.start()
        self._stopping.clear()
        self._pinger = threading.Thread(target=self._ping, name="proper-cable-ping", daemon=True)
        self._pinger.start()

    def stop(self, grace: float) -> None:
        self._stopping.set()
        t.cast(threading.Thread, self._pinger).join()
        self._pinger = None
        self.server.stop(grace)
        self.server.wait()

    def _ping(self) -> None:
        while not self._stopping.wait(self.ping_interval):
            self.server.publish(ALL, PING)

    # Bearings' events

    def opened(self, ws: int, environ: dict) -> None:
        with self._lock:
            self._open.add(ws)
        self.server.subscribe(ws, ALL)
        address, port = environ.get("REMOTE_ADDR", ""), environ.get("REMOTE_PORT", "")
        if address and ":" in address:
            address = f"[{address}]"
        self.cable._handle_event("connect", ws, {
            "path": environ.get("RAW_URI") or "/",
            "cookies": environ.get("HTTP_COOKIE"),
            "authorization": environ.get("HTTP_AUTHORIZATION"),
            "forwarded_for": environ.get("HTTP_X_FORWARDED_FOR"),
            "remote_addr": f"{address}:{port}" if address else "",
        })

    def received(self, ws: int, message: str | bytes) -> None:
        if isinstance(message, bytes):
            message = message.decode(errors="replace")
        self.cable._handle_event("raw", ws, message)

    def closed(self, ws: int, code: int, reason: str) -> None:
        self._forget(ws)
        self.cable._handle_event("disconnect", ws, "")

    # The transport

    def _write(self, conn_id: int, text: str) -> None:
        if not self.server.ws_send(conn_id, text) and conn_id in self._open:
            # Too far behind to take more: closed, so it reconnects and
            # recovers instead of missing messages without knowing.
            self.server.ws_close(conn_id, TOO_FAR_BEHIND, "too far behind")

    def _fanout(self, topic: str, text: str) -> None:
        self.server.publish(_topic(topic), text)

    def _joined(self, conn_id: int, topic: str) -> None:
        self.server.subscribe(conn_id, _topic(topic))

    def _left(self, conn_id: int, topic: str) -> None:
        self.server.unsubscribe(conn_id, _topic(topic))

    def disconnect(self, conn_id: int) -> None:
        self.server.ws_close(conn_id)



def _no_http(environ: dict, start_response: t.Callable) -> list[bytes]:
    """The cable's port answers only WebSockets on `CABLE_PATH`."""
    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found\n"]


class Cable(BaseCable):
    """See the module."""

    # `proper run` starts it, in its web process (`start_server()`).
    serves_websockets = True
    # Other processes forward their broadcasts here over HTTP (RedisCable
    # doesn't: they publish to Redis).
    takes_forwarded = True

    def __init__(
        self,
        *,
        port: int | None = None,
        host: str = "0.0.0.0",
        forward_port: int | None = None,
        loops: int = 1,
        workers: int = 4,
        max_connections: int = 100_000,
        idle_timeout: float = 60,
        recovery: bool = True,
        recovery_buffer_size: int = 128,
        recovery_ttl: float = 300,
        recovery_memory_budget: int = 256 * 1024 * 1024,
        presence: bool = True,
        presence_max_data_size: int = 4096,
        presence_max_members: int = 0,
        shutdown_grace: float = 1,
    ) -> None:
        """`loops`: Bearings' event loops, the threads that read and write
        the WebSockets. `workers`: the threads that run the channels.

        `idle_timeout`: seconds; a connection that answers no ping for that
        long is closed (`cable.js` answers them).

        `recovery`: keep the last `recovery_buffer_size` broadcasts of each
        stream, so a client that reconnects gets the ones it missed (see
        `_subscribe`). A stream's are dropped after `recovery_ttl` seconds
        without a broadcast, and, past `recovery_memory_budget` bytes for all
        of them, those of the streams with the oldest last broadcast.

        `presence`: keep who is in each stream (`Channel.track()`). The data
        of a user may be `presence_max_data_size` bytes at most, as JSON, and
        a stream may have `presence_max_members` users (`0`: no limit).

        `shutdown_grace`: seconds the WebSockets have to close when the
        server stops; the ones still open then are cut."""
        super().__init__()
        self.app: "App" = None  # ty: ignore[invalid-assignment] - set by `bind()`
        self.server: t.Any = None
        self._host = host
        self._port = port
        self._forward_port = forward_port
        self._loops = loops
        self._workers = workers
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout
        self._recovery = recovery
        self._recovery_buffer_size = recovery_buffer_size
        self._recovery_ttl = recovery_ttl
        self._recovery_memory_budget = recovery_memory_budget
        self._presence = presence
        self._presence_max_data_size = presence_max_data_size
        self._presence_max_members = presence_max_members
        self._shutdown_grace = shutdown_grace
        self._start_lock = threading.Lock()
        # The process that started the server; a forked copy of it has none.
        self._owner_pid: int | None = None
        self._receiver: _ForwardedServer | None = None
        self._connections: dict[t.Any, Connection] = {}  # type: ignore[assignment]
        self._users: dict[t.Any, set[Connection]] = {}
        # (conn_id, stream) -> how many channels of the connection stream it
        self._stream_refs: dict[tuple[t.Any, str], int] = {}
        # Runs a connection's commands: in the thread that brings them, which
        # is one of Bearings' workers (in order, one at a time per connection)
        # or, in memory, the test's.
        self._executor = _InlineExecutor()

    def bind(self, app: "App") -> None:
        self.app = app
        port = self._ws_port()
        if port:
            path = app.config.get("CABLE_PATH", "/cable")
            self.forward_to(
                f"http://127.0.0.1:{self._forward_port or port + 1}{path}",
                sign=partial(app.dumps, salt=CABLE_SALT),
            )

    def _ws_port(self) -> int:
        return int(self._port or self.app.config.get("CABLE_PORT") or 0)

    @property
    def serving(self) -> bool:
        """Whether this process serves the WebSockets."""
        return self.server is not None and self._owner_pid == os.getpid()

    @property
    def _forwarding(self) -> bool:
        return bool(self._forward_url) and not self.serving

    # Lifecycle

    def start_server(self) -> None:
        """Serve the WebSockets from this process, and take the broadcasts
        the other processes forward. Returns once both listen; raises
        `OSError`, with the reason, when a port can't be listened on.
        `proper run` calls it."""
        with self._start_lock:
            if self.serving:
                return
            port = self._ws_port()
            if not port:
                raise RuntimeError("Cable needs a port: set CABLE_PORT")
            receiver = None
            if self.takes_forwarded:  # bound first: a port taken fails before the rest
                receiver = _ForwardedServer(
                    ("127.0.0.1", self._forward_port or port + 1), _ForwardedHandler
                )
                receiver.cable = self
            server = BearingsServer(self, port)
            try:
                server.start()
            except BaseException:
                if receiver is not None:
                    receiver.server_close()
                raise
            self.server = server
            self._owner_pid = os.getpid()
            self._receiver = receiver
            if receiver is not None:
                threading.Thread(
                    target=receiver.serve_forever, args=(0.1,), name="proper-cable-forwarded",
                    daemon=True,
                ).start()
            logger.info("[cable] listening on %s:%s", self._host, port)

    def health(self) -> dict[str, t.Any]:
        """How the cable is doing (see `BaseCable.health`). Serving, it adds
        the server's counters (`connections`, and the streams with a recovery
        buffer and with presence) under `server`, and the `streams`
        subscribed here:

        ```python
        @router.get("/up")
        def up(self):
            return self.render_json(self.app.cable.health())
        ```
        """
        if not self.serving:
            return super().health()
        with self._lock:
            connections = len(self._connections)
            users = len(self._users)
        return {
            "serving": True,
            "connections": connections,
            "users": users,
            "streams": len(self.streams),
            "server": dict(self.server.health_snapshot()),
        }

    def metrics(self) -> str:
        """The cable's metrics in Prometheus' text format:
        `proper_cable_connections`, `proper_cable_streams` and
        `proper_cable_users`. Served on the loopback port the other
        processes forward to (`CABLE_PORT + 1`) as `GET /metrics`, for
        Prometheus to scrape; empty where nothing is served."""
        if not self.serving:
            return ""
        with self._lock:
            users = len(self._users)
        return (
            self.server.prometheus_metrics()
            + "# HELP proper_cable_streams Streams with a subscription here\n"
            "# TYPE proper_cable_streams gauge\n"
            f"proper_cable_streams {len(self.streams)}\n"
            "# HELP proper_cable_users Connections with a logged-in user, by user\n"
            "# TYPE proper_cable_users gauge\n"
            f"proper_cable_users {users}\n"
        )

    def serve_in_memory(self) -> "InMemoryServer":
        """Serve from memory instead of a port, for tests: no socket, no
        threads; each event and command runs in the thread that causes it,
        through the same code as the real server's. `TestClient.websocket()`
        calls it."""
        with self._start_lock:
            if isinstance(self.server, InMemoryServer):
                return self.server
            if self.serving:
                raise RuntimeError("Cable is already serving on a port")
            server = InMemoryServer(self)
            self.server = server
            self._owner_pid = os.getpid()
            return server

    def stop_server(self) -> None:
        """Stop serving. The channels of the connections still open end
        first (`unsubscribed()`), then the WebSockets close."""
        with self._start_lock:
            server = self.server
            if server is None or not self.serving:
                return
            if isinstance(server, InMemoryServer):
                self._end_open_connections()
                self.server = None
                self._owner_pid = None
                return
            receiver = self._receiver
            if receiver is not None:
                receiver.shutdown()
                receiver.server_close()
                self._receiver = None
            self._end_open_connections()
            server.stop(self._shutdown_grace)
            self.server = None
            self._owner_pid = None

    def _end_open_connections(self) -> None:
        """The connections still open end here: their channels'
        `unsubscribed()` runs, as it would have on a disconnect."""
        for conn in list(self._connections.values()):
            conn.closing = True
            conn.enqueue(_DISCONNECT)
        self._connections.clear()

    def _handle_event(self, kind: str, conn_id: t.Any, payload: t.Any) -> None:
        """One event of the server: a connection, a message, a disconnect."""
        connections = self._connections
        if kind == "connect":
            connections[conn_id] = Connection(self, conn_id, payload)
            return
        conn = connections.get(conn_id)
        if conn is None:  # ended by `stop_server()` while the event came
            return
        if kind == "raw":
            try:
                conn.enqueue(json.loads(payload))
            except ValueError:
                conn.put({"type": "error", "reason": "invalid_json"})
        elif kind == "disconnect":  # pragma: no branch - other kinds are ignored
            del connections[conn_id]
            conn.closing = True
            conn.enqueue(_DISCONNECT)

    # Streams

    def subscribe(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(Connection, channel._connection)
        key = (conn.conn_id, stream_name)
        with self._lock:
            refs = self._stream_refs.get(key, 0)
            self._stream_refs[key] = refs + 1
        if not refs:
            self.server.subscribe_connection(conn.conn_id, [stream_name])

    def unsubscribe(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(Connection, channel._connection)
        key = (conn.conn_id, stream_name)
        with self._lock:
            refs = self._stream_refs.get(key, 0) - 1
            if refs > 0:
                self._stream_refs[key] = refs
                return
            self._stream_refs.pop(key, None)
        if not conn.closing:
            try:
                self.server.unsubscribe_connection(conn.conn_id, [stream_name])
            except RuntimeError:  # pragma: no cover - unsubscribing as the server stops
                pass

    def unsubscribe_all(self, channel: "Channel") -> None:
        for stream_name in list(getattr(channel, "_streams", ())):
            self.unsubscribe(stream_name, channel)

    @property
    def streams(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._lock:
            for (_, stream), refs in self._stream_refs.items():
                counts[stream] = counts.get(stream, 0) + refs
        return counts

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        if self.serving:
            self._deliver_local(stream_name, data)
        else:
            super().broadcast(stream_name, data)  # forwarded, maybe batched

    def _deliver_local(self, stream_name: str, data: t.Any) -> None:
        if not self.serving:
            logger.warning(
                "⚠️ [cable] no WebSocket server here or to forward to: "
                "the broadcast to %s is lost", stream_name,
            )
            return
        self._send_frame(stream_name, _broadcast_frame(stream_name, data))

    def _send_frame(self, stream_name: str, frame: str) -> None:
        """Hand an encoded broadcast to the server."""
        self.server.broadcast_local(stream_name, frame)

    # Presence

    def track(self, stream_name: str, data: dict, channel: "Channel", key: t.Any = None) -> None:
        conn = t.cast(Connection, channel._connection)
        self._check_presence_data(data)
        conn.presence_identity(key)
        limit = self._presence_max_members
        if limit:
            present = self.presence(stream_name)
            if conn.presence_key not in present and len(present) >= limit:
                raise ValueError(
                    f"{stream_name!r} already has {limit} present: presence_max_members"
                )
        self.server.subscribe_connection(conn.conn_id, [stream_name], data)

    def _check_presence_data(self, data: t.Any) -> None:
        size = len(jsonplus.dumps(data).encode())
        if size > self._presence_max_data_size:
            raise ValueError(
                f"the presence data is {size} bytes as JSON, more than "
                f"presence_max_data_size ({self._presence_max_data_size})"
            )

    def _presence_changed(
        self, kind: str, stream_name: str, user: str, data: t.Any, connections: int
    ) -> None:
        """What `_Streams` calls when presence changes here: a user's first
        connection to the stream (`"join"`), their last one gone (`"leave"`),
        new data (`"update"`), or another connection count (`"connections"`).
        The stream's subscribers hear of the first three."""
        if kind != "connections":
            self.server._presence_frame(f"presence_{kind}", stream_name, user, data)

    def untrack(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(Connection, channel._connection)
        if conn.presence_key is not None and not conn.closing:
            self.server.untrack_presence(conn.conn_id, [stream_name])

    def update_presence(self, channel: "Channel", data: dict) -> None:
        conn = t.cast(Connection, channel._connection)
        if conn.presence_key is None:
            raise ValueError("the connection is not present anywhere: track() first")
        self._check_presence_data(data)
        self.server.update_presence(conn.conn_id, data)

    def presence(self, stream_name: str) -> dict[str, dict]:
        if not self.serving or not self._presence:
            return {}
        return self.server.presence(stream_name)

    def presence_stats(self, stream_name: str) -> dict[str, int]:
        present = self.presence(stream_name)
        return {
            "users": len(present),
            "connections": sum(entry["connections"] for entry in present.values()),
        }

    # Users

    def _register(self, connection) -> None:
        with self._lock:
            self._users.setdefault(connection.user_id, set()).add(connection)

    def _unregister(self, connection) -> None:
        with self._lock:
            users = self._users.get(connection.user_id)
            if users is not None:
                users.discard(connection)
                if not users:
                    del self._users[connection.user_id]

    def _disconnect_local(self, who: dict) -> None:
        with self._lock:
            connections = list(self._users.get(who.get("user_id"), ()))
        for connection in connections:
            connection.close_threadsafe()

    # Commands, in a worker thread, one connection at a time

    def _command(self, conn: Connection, msg: t.Any) -> None:
        if not isinstance(msg, dict):
            conn.put({"type": "error", "reason": "invalid_message"})
            return
        command = msg.get("command")
        channel_name = msg.get("channel", "")
        params = msg.get("params") or {}
        key = _subscription_key(channel_name, params)
        if command == "subscribe":
            self._subscribe(conn, channel_name, params, key, _client_positions(msg.get("positions")))
        elif command == "unsubscribe":
            channel = conn.subscriptions.pop(key, None)
            if channel is not None:
                channel.stop_all_streams()
                self.app._with_db(lambda: channel._dispatch("unsubscribed"))
        elif command == "message":
            self._message(conn, msg, key)
        else:
            conn.put({"type": "error", "reason": "unknown_command"})

    def _subscribe(self, conn, channel_name, params, key, positions) -> None:
        """Subscribe, or confirm again a subscription that exists. With
        `positions`, where the client last was in some streams, the broadcasts
        it missed in the ones the channel streams from are sent to it."""
        confirm = {"type": "confirm_subscription", "channel": channel_name, "params": params}
        existing = conn.subscriptions.get(key)
        if existing is not None:
            self._confirm(conn, confirm, existing, positions)
            return
        channel_cls = self.app.router.channels.get(channel_name)
        if channel_cls is None:
            conn.put({
                "type": "reject_subscription", "channel": channel_name,
                "params": params, "reason": "unknown_channel",
            })
            return
        # Held back until the subscription is settled: a rejected channel
        # must not reach the client. Nothing else sends to this connection
        # meanwhile: its commands run one at a time.
        pending: list = []
        channel = channel_cls(
            self.app, params, request=conn.request, name=channel_name,
            _send=pending.append, _connection=conn,
        )
        reject = {"type": "reject_subscription", "channel": channel_name, "params": params}
        try:
            self.app._with_db(lambda: channel._dispatch("subscribed"))
        except Exception:
            # Not subscribed: the streams it reached before failing must
            # not stay open. Raised again, to be logged.
            channel.stop_all_streams()
            conn.put({**reject, "reason": "error"})
            raise
        if channel._rejected:
            channel.stop_all_streams()
            conn.put(reject)
            return
        conn.subscriptions[key] = channel
        channel._send = conn.put
        for msg in pending:
            conn.put(msg)
        self._confirm(conn, confirm, channel, positions)

    def _confirm(self, conn, confirm: dict, channel, positions) -> None:
        """Confirm the subscription, with its streams, where each of them is
        now (`positions`, `null` for one without broadcasts yet), and whether
        the broadcasts the client missed were all sent to it (`recovered`:
        `null` when it asked for none). The missed ones are written straight
        to the connection by the server, so they can arrive before this."""
        streams = sorted(channel._streams)
        current: dict[str, dict | None] = dict.fromkeys(streams)
        recovered: bool | None = None
        if self._recovery and streams:
            server = self.server
            to_recover = [stream for stream in streams if stream in positions]
            if to_recover:
                recovered = True
            for stream in to_recover:
                # One call per epoch the client saw: a server that started
                # again, or another machine, gives a stream a new one
                for epoch, offset in positions[stream]:
                    result = server.subscribe_with_recovery(
                        conn.conn_id, [stream], recover=True, epoch=epoch, offset=offset
                    )
                    recovered = recovered and result["recovered"]
                current[stream] = _position(result["topics"][stream])
            rest = [stream for stream in streams if stream not in positions]
            if rest:
                result = server.subscribe_with_recovery(conn.conn_id, rest)
                for stream in rest:
                    current[stream] = _position(result["topics"][stream])
        present = {
            stream: {key: entry["data"] for key, entry in self.presence(stream).items()}
            for stream in sorted(channel._tracked)
        }
        conn.put({
            **confirm, "streams": streams, "positions": current, "recovered": recovered,
            "presence": present,
        })

    def _message(self, conn, msg, key) -> None:
        """Run an action. A message with an `id` gets a reply: what the
        action returned, or the error that stopped it."""
        msg_id = msg.get("id")

        def fail(reason: str, **data: t.Any) -> None:
            if msg_id is None:
                conn.put({"type": "error", "reason": reason, **data})
            else:
                conn.put({
                    "type": "reply", "id": msg_id, "channel": msg.get("channel", ""),
                    "params": msg.get("params") or {},
                    "status": "error", "data": {"reason": reason, **data},
                })

        channel = conn.subscriptions.get(key)
        if channel is None:
            fail("not_subscribed")
            return
        action = msg.get("action", "")
        if not action or action.startswith("_") or action in _BLOCKED_ACTIONS:
            fail("invalid_action")
            return
        if not callable(getattr(channel, action, None)):
            fail("unknown_action")
            return
        data = msg.get("data") or {}
        # An `ActionError` is the action's answer, not a failure to log.
        failed: list[ActionError] = []

        def on_error(error: Exception) -> None:
            if not isinstance(error, ActionError):
                raise error
            failed.append(error)

        try:
            result = self.app._with_db(
                lambda: channel._dispatch(action, data), on_error=on_error
            )
        except Exception:
            # The client learns that it failed, not why: that goes to the log.
            fail("error")
            raise
        if failed:
            fail(**failed[0].data)
        elif msg_id is not None:
            conn.put({
                "type": "reply", "id": msg_id, "channel": channel.channel_name,
                "params": channel.params, "status": "ok", "data": result,
            })

    def _cleanup(self, conn: Connection) -> None:
        self._unregister(conn)
        for channel in conn.subscriptions.values():
            try:
                channel.stop_all_streams()
                self.app._with_db(lambda ch=channel: ch._dispatch("unsubscribed"))
            except Exception:
                logger.exception("Error in %s.unsubscribed", channel.channel_name)
        conn.subscriptions.clear()
