"""The cable: the WebSockets of the channels, served by a Rust engine.

`subscribed()`, the actions and `unsubscribed()` of the channels run in
Python, in worker threads, and decide what each connection streams from.
Under them:

- The WebSockets are served by wse-server (`wse_server.RustWSEServer`, tokio
  and tungstenite) on `CABLE_PORT`, inside the web process. No second process,
  and a `broadcast()` made by a controller needs no forwarding.
- A stream is a wse topic. `stream_from()` subscribes the connection to it,
  and `broadcast()` hands the encoded frame to wse, which writes it to every
  subscriber without Python: one frame, built once.
- Because a broadcast is the same text for every subscriber, its frame names
  the stream, not the channel and params of each subscription:
  `{"c": "P", "type": "broadcast", "stream": ..., "data": ...}`. The
  confirmation of a subscription lists its streams, so the client routes by
  stream. Messages sent with `send()` keep their channel and params.

```python
CABLE = {"type": "proper.channels.Cable"}   # serves on CABLE_PORT
```

Without the channels addon, `CABLE = {}` is a `BaseCable` (`base.py`): no
WebSockets, and a broadcast reaches no one.

On several machines, the web process of each joins wse's cluster, a TCP
mesh between the servers (`cluster` option): a broadcast made on one
machine reaches the subscribers of all, presence is one list, and the
recovery buffers know the other machines' broadcasts. `disconnect()`
reaches every machine through a topic the servers themselves listen to
(`CONTROL_TOPIC`, `subscribe_node`).

`proper run` starts the server, in its web process, before it serves the
first request (`start_server()`; call it yourself under another server).
Every other process that loads the app (the copies of `PROCESSES`, a task
worker, a shell) has no WebSockets: its broadcasts and `disconnect()`s are
forwarded to that one, signed with the app's keys, over HTTP on
`127.0.0.1:forward_port` (`CABLE_PORT + 1` unless given).

wse pings every connection each `CABLE_PING_INTERVAL` seconds
(`{"c": "WSE", "t": "ping"}`), which `cable.js` answers and uses to notice
a dead connection; one that answers no ping for `idle_timeout` seconds (60)
is closed. Handshakes from other sites' pages are refused (see
`origin_allowed`). Requires `proper-wse` (`uv add proper-wse`), our fork
of wse-server, with wheels for free-threaded Python; it imports as
`wse_server`, and the original wse-server is refused.
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
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
# The topic the servers of a cluster listen to themselves, for what one
# machine tells the others (`disconnect()`).
CONTROL_TOPIC = "proper:cable:control"


def _client_positions(value: t.Any) -> dict[str, list[tuple[str, int]]]:
    """The positions a `subscribe` command carries, `{stream: [{"e": epoch,
    "o": offset}, ...]}` (or one `{"e", "o"}`), as `{stream: [(epoch,
    offset), ...]}`; the malformed ones left out. The epoch is wse's: eight
    hex digits. Several per stream, because in a cluster each machine
    stamps what it publishes with its own epoch."""
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
    """A stream's position as the client gets it, from what wse returned."""
    if topic_result.get("epoch") is None:
        return None
    return {"e": topic_result["epoch"], "o": topic_result["offset"]}


def _stamp(frame: str, topic: str, epoch: str, offset: int) -> str:
    """Stamp a frame as wse does when recovery is on: the topic, the epoch
    of its buffer and the offset of the message, first."""
    return '{"tp": %s, "e": "%s", "o": %d, %s' % (jsonplus.dumps(topic), epoch, offset, frame[1:])


def _handshake_request(app: "App", details: dict) -> t.Any:
    """The handshake as a request, for the channels: its path and query
    string, its `Cookie`, `Authorization` and `X-Forwarded-For` headers, and
    the client's address (`request.remote_ip`). `details` is what wse gives
    with `handshake_details`."""
    path, _, query_string = str(details.get("path") or "/").partition("?")
    headers = [
        (name, value)
        for name, value in (
            ("cookie", details.get("cookies")),
            ("authorization", details.get("authorization")),
            ("x-forwarded-for", details.get("forwarded_for")),
        )
        if value
    ]
    host, _, port = str(details.get("remote_addr") or "").rpartition(":")
    client = (host.strip("[]"), int(port)) if host and port.isdigit() else None
    return app.request_cls(
        method="GET", path=path, query_string=query_string, headers=headers,
        client=client, app=app,
    )


class WseConnection:
    """One WebSocket of the wse server, as the channels see it."""

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
    """Takes the broadcasts other processes forward (`Cable._forward`)."""

    protocol_version = "HTTP/1.1"  # the senders keep their connection open
    server: "_ForwardedServer"

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
    """The recovery buffer of a topic, as `InMemoryServer` keeps it."""

    __slots__ = ("epoch", "offset", "frames")

    def __init__(self, size: int) -> None:
        self.epoch = secrets.token_hex(4)
        self.offset = -1  # of the last message
        self.frames: deque[tuple[int, str]] = deque(maxlen=size)


class _Present:
    """A user present in a topic, as `InMemoryServer` keeps it."""

    __slots__ = ("data", "connections")

    def __init__(self, data: dict) -> None:
        self.data = data
        self.connections: set[str] = set()


class InMemoryServer:
    """The parts of `wse_server.RustWSEServer` that `Cable` uses, in
    memory, for tests (`Cable.serve_in_memory()`). A connection is a queue
    of the text frames written to it; `None` marks that the server closed it.
    The client side (`connect`, `client_send`, `client_close`, `frames`) is
    what `TestClient.websocket()` drives."""

    def __init__(self, cable: "Cable") -> None:
        self.cable = cable
        self._lock = threading.Lock()
        # Kept after a connection closes, so its client can read the rest.
        self._frames: dict[str, "queue.Queue[str | None]"] = {}
        self._open: set[str] = set()
        self._topics: dict[str, set[str]] = {}
        self._count = 0
        # Recovery, as wse keeps it: per topic, the epoch of its buffer, the
        # offset of the last message, and the last `buffer_size` frames.
        self.recovery_enabled = cable._recovery
        self.buffer_size = int(cable._server_options.get("recovery_buffer_size") or 128)
        self._buffers: dict[str, _Buffer] = {}
        # Presence, as wse keeps it: a connection's user, and per topic and
        # user, their data and connections.
        self.presence_enabled = cable._presence
        self._users: dict[str, str] = {}
        self._presence: dict[str, dict[str, _Present]] = {}

    # The client side

    def connect(self, details: dict | None = None) -> str:
        """A client connects. `details` is the handshake as wse reports it
        with `handshake_details`: `cookies`, `authorization`, `path` (with
        the query string), `remote_addr` and `forwarded_for`."""
        with self._lock:
            self._count += 1
            conn_id = f"memory-{self._count}"
            self._frames[conn_id] = queue.Queue()
            self._open.add(conn_id)
        self.cable._handle_event("connect", conn_id, details or {})
        return conn_id

    def client_send(self, conn_id: str, text: str) -> None:
        """A text frame from the client, sorted as wse sorts it."""
        try:
            self.cable._handle_event("msg", conn_id, json.loads(text))
        except ValueError:
            self.cable._handle_event("raw", conn_id, text)

    def client_close(self, conn_id: str) -> None:
        if self._close(conn_id):
            self.cable._handle_event("disconnect", conn_id, "")

    def frames(self, conn_id: str) -> "queue.Queue[str | None]":
        return self._frames[conn_id]

    def is_open(self, conn_id: str) -> bool:
        return conn_id in self._open

    # What Cable calls

    def send(self, conn_id: str, text: str) -> None:
        if conn_id in self._open:
            self._frames[conn_id].put(text)

    def subscribe_connection(
        self, conn_id: str, topics: list[str], presence_data: dict | None = None
    ) -> None:
        with self._lock:
            for topic in topics:
                self._topics.setdefault(topic, set()).add(conn_id)
        # With presence data, the connection is listed in the topics, as the
        # user `set_connection_user` gave it; wse skips one without a user.
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
            if first:
                self._presence_frame("presence_join", topic, user, presence_data)

    def unsubscribe_connection(self, conn_id: str, topics: list[str]) -> None:
        with self._lock:
            for topic in topics:
                self._topics.get(topic, set()).discard(conn_id)
        self.untrack_presence(conn_id, topics)

    # Presence (`presence_enabled`)

    def set_connection_user(self, conn_id: str, user_id: str) -> None:
        self._need_presence()
        self._users[conn_id] = user_id

    def untrack_presence(self, conn_id: str, topics: list[str]) -> None:
        self._need_presence()
        for topic in topics:
            with self._lock:
                members = self._presence.get(topic, {})
                gone = [
                    (user, entry.data) for user, entry in members.items()
                    if conn_id in entry.connections
                    and not (entry.connections.discard(conn_id) or entry.connections)
                ]
                for user, _ in gone:
                    del members[user]
            for user, data in gone:
                self._presence_frame("presence_leave", topic, user, data)

    def update_presence(self, conn_id: str, data: dict) -> None:
        self._need_presence()
        user = self._users.get(conn_id)
        if user is None:
            raise RuntimeError("Failed to update presence data (size limit or unknown connection)")
        for topic, members in list(self._presence.items()):
            if user in members and conn_id in members[user].connections:
                members[user].data = data
                self._presence_frame("presence_update", topic, user, data)

    def presence(self, topic: str) -> dict:
        with self._lock:
            return {
                user: {"data": entry.data, "connections": len(entry.connections)}
                for user, entry in self._presence.get(topic, {}).items()
            }

    def presence_stats(self, topic: str) -> dict:
        with self._lock:
            members = self._presence.get(topic, {})
            return {
                "num_users": len(members),
                "num_connections": sum(len(e.connections) for e in members.values()),
            }

    def _need_presence(self) -> None:
        if not self.presence_enabled:
            raise RuntimeError("Presence is not enabled")

    def _presence_frame(self, kind: str, topic: str, user: str, data: dict) -> None:
        """A presence event, to the subscribers of the topic, as wse writes it."""
        text = jsonplus.dumps({
            "c": "WSE", "t": kind, "p": {"topic": topic, "user_id": user, "data": data},
        })
        with self._lock:
            conn_ids = list(self._topics.get(topic, ()))
        for conn_id in conn_ids:
            self.send(conn_id, text)

    def broadcast_local(self, topic: str, text: str) -> None:
        with self._lock:
            conn_ids = list(self._topics.get(topic, ()))
            if self.recovery_enabled:
                buffer = self._buffers.get(topic)
                if buffer is None:
                    buffer = self._buffers[topic] = _Buffer(self.buffer_size)
                buffer.offset += 1
                text = _stamp(text, topic, buffer.epoch, buffer.offset)
                buffer.frames.append((buffer.offset, text))
        for conn_id in conn_ids:
            self.send(conn_id, text)

    def subscribe_with_recovery(
        self, conn_id: str, topics: list[str], recover: bool = False,
        epoch: str | None = None, offset: int | None = None,
    ) -> dict:
        """Subscribe, and with `recover`, write to the connection the frames
        of the topics after `offset` in `epoch`. Returns, as wse does, the
        position of each topic and whether it was recovered."""
        self.subscribe_connection(conn_id, topics)
        result: dict[str, t.Any] = {"recovered": recover and bool(topics), "topics": {}}
        for topic in topics:
            with self._lock:
                buffer = self._buffers.get(topic)
                frames = list(buffer.frames) if buffer else []
            recovered = False
            if buffer is None:
                position: dict[str, t.Any] = {"epoch": None, "offset": 0, "recoverable": False}
            else:
                position = {"epoch": buffer.epoch, "offset": buffer.offset, "recoverable": True}
                oldest = frames[0][0]  # a buffer is made with its first frame
                if recover and epoch == buffer.epoch and offset is not None and offset >= oldest - 1:
                    for frame_offset, text in frames:
                        if frame_offset > offset:
                            self.send(conn_id, text)
                    recovered = True
            if not recovered:
                result["recovered"] = False
            result["topics"][topic] = {**position, "recovered": recovered}
        return result

    def broadcast_all(self, text: str) -> None:
        for conn_id in list(self._open):
            self.send(conn_id, text)

    # A cluster of one, for tests of a cable configured with one
    broadcast = broadcast_local

    def cluster_info(self) -> list:
        return []

    def health_snapshot(self) -> dict:
        with self._lock:
            return {
                "connections": len(self._open),
                "inbound_queue_depth": 0,
                "inbound_dropped": 0,
                "recovery_enabled": self.recovery_enabled,
                "recovery_topic_count": len(self._buffers),
                "presence_enabled": self.presence_enabled,
                "presence_topics": len(self._presence),
                "cluster_connected": False,
                "cluster_peer_count": 0,
            }

    def disconnect(self, conn_id: str) -> None:
        """The server closes a connection; the client sees it end."""
        if self._close(conn_id, notify=True):
            self.cable._handle_event("disconnect", conn_id, "")

    def topic_backlog(self, topic: str) -> tuple[int, int, int]:
        with self._lock:
            return (len(self._topics.get(topic, ())), 0, 0)  # delivered at once

    def _close(self, conn_id: str, notify: bool = False) -> bool:
        with self._lock:
            if conn_id not in self._open:
                return False
            self._open.discard(conn_id)
            for conn_ids in self._topics.values():
                conn_ids.discard(conn_id)
            tracked = [topic for topic, members in self._presence.items()
                       if any(conn_id in e.connections for e in members.values())]
        if tracked:
            self.untrack_presence(conn_id, tracked)
        self._users.pop(conn_id, None)
        if notify:
            self._frames[conn_id].put(None)
        return True


class Cable(BaseCable):
    """See the module."""

    # `proper run` starts it, in its web process (`start_server()`).
    serves_websockets = True

    def __init__(
        self,
        *,
        port: int | None = None,
        host: str = "0.0.0.0",
        forward_port: int | None = None,
        workers: int = 4,
        max_connections: int = 100_000,
        max_outbound_queue_bytes: int = 64 * 1024 * 1024,
        backpressure_bytes: int = 128 * 1024,
        backpressure_timeout: float = 1.0,
        recovery: bool = True,
        presence: bool = True,
        cluster: dict | None = None,
        **server_options: t.Any,
    ) -> None:
        """`recovery`: keep the last broadcasts of each stream, so a client
        that reconnects gets the ones it missed (see `_subscribe`). wse's
        `recovery_buffer_size` (128 per stream), `recovery_ttl` (300 seconds)
        and `recovery_memory_budget` (256 MB) size the buffers.

        `presence`: keep who is in each stream (`Channel.track()`). wse's
        `presence_max_data_size` (4 KB per user) and `presence_max_members`
        (0: no limit) bound it.

        `cluster`: join the servers of the other machines (see the module):
        `{"port": 9999, "peers": ["10.0.0.2:9999", ...]}`, or `"seeds"` and
        `"addr"` (this machine's `host:port`) for discovery by gossip, and
        `"tls": {"cert", "key", "ca"}` for mTLS between them (without it,
        plain TCP: only on a private network).

        `max_outbound_queue_bytes` is how far behind a connection can fall
        before wse drops broadcasts for it. The default is four times wse's:
        a broadcast frame is shared by every connection it goes to, so a
        backlog costs memory once, not once per connection.

        `backpressure_bytes`: a broadcast waits while the subscribers of its
        stream have more than this many bytes each, on average, queued and
        not yet written; so whoever publishes (a request, a channel action)
        slows down to the pace of delivery, instead of a backlog growing and
        every message arriving later. The average, so that one stalled client
        doesn't hold everyone back. It waits `backpressure_timeout` seconds at
        most, less than a forwarded broadcast's timeout. `0` never waits."""
        super().__init__()
        self.app: "App" = None  # ty: ignore[invalid-assignment] - set by `bind()`
        self.server: t.Any = None
        self._host = host
        self._port = port
        self._forward_port = forward_port
        self._max_connections = max_connections
        self._recovery = recovery
        self._presence = presence
        self._cluster = cluster
        self._server_options = {
            "max_outbound_queue_bytes": max_outbound_queue_bytes,
            "recovery_enabled": recovery, "presence_enabled": presence, **server_options,
        }
        self._workers = workers
        self._backpressure_bytes = backpressure_bytes
        self._backpressure_timeout = backpressure_timeout
        self._start_lock = threading.Lock()
        # The process that started the server; a forked copy of it has none.
        self._owner_pid: int | None = None
        self._receiver: _ForwardedServer | None = None
        self._stopping = threading.Event()
        self._watcher: threading.Thread | None = None
        self._connections: dict[str, WseConnection] = {}  # type: ignore[assignment]
        self._users: dict[t.Any, set[WseConnection]] = {}
        # (conn_id, stream) -> how many channels of the connection stream it
        self._stream_refs: dict[tuple[str, str], int] = {}
        self._executor: ThreadPoolExecutor = None  # ty: ignore[invalid-assignment] - set by `start_server()`
        self._draining = False
        self._drain_thread: threading.Thread | None = None

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
        the other processes forward. `proper run` calls it."""
        with self._start_lock:
            if self.serving:
                return
            port = self._ws_port()
            if not port:
                raise RuntimeError("Cable needs a port: set CABLE_PORT")
            # Bound first: a port already taken fails here, before anything runs.
            receiver = _ForwardedServer(
                ("127.0.0.1", self._forward_port or port + 1), _ForwardedHandler
            )
            receiver.cable = self
            try:
                server = self._new_server(port)
            except BaseException:
                receiver.server_close()
                raise
            server.enable_drain_mode()
            server.start()
            if self._cluster:
                try:
                    self._join_cluster(server)
                except BaseException:
                    server.stop()
                    receiver.server_close()
                    raise
            self._executor = ThreadPoolExecutor(
                self._workers, thread_name_prefix="proper-cable"
            )
            self.server = server
            self._owner_pid = os.getpid()
            self._stopping.clear()
            self._draining = True
            self._drain_thread = threading.Thread(
                target=self._drain, name="proper-cable-drain", daemon=True
            )
            self._drain_thread.start()
            self._receiver = receiver
            threading.Thread(
                target=receiver.serve_forever, args=(0.1,), name="proper-cable-forwarded",
                daemon=True,
            ).start()
            limit = int(self.app.config.get("CABLE_MAX_PENDING_BYTES") or 0)
            if limit > 0:
                stall = float(self.app.config.get("CABLE_STALL_TIMEOUT") or 10)
                self._watcher = threading.Thread(
                    target=self._watch, args=(limit, stall), name="proper-cable-watch",
                    daemon=True,
                )
                self._watcher.start()
            logger.info("[cable] wse-server listening on %s:%s", self._host, port)

    def _join_cluster(self, server: t.Any) -> None:
        cluster = t.cast(dict, self._cluster)
        tls = cluster.get("tls") or {}
        server.subscribe_node([CONTROL_TOPIC])
        server.connect_cluster(
            peers=list(cluster.get("peers") or ()),
            tls_cert=tls.get("cert"), tls_key=tls.get("key"), tls_ca=tls.get("ca"),
            cluster_port=cluster["port"],
            seeds=list(cluster.get("seeds") or ()) or None,
            cluster_addr=cluster.get("addr"),
        )
        logger.info("[cable] in a cluster, on port %s", cluster["port"])

    def health(self) -> dict[str, t.Any]:
        """How the cable is doing (see `BaseCable.health`). Serving, it adds
        what wse reports (`health_snapshot()`: `inbound_queue_depth`,
        `inbound_dropped`, `uptime_secs`, the recovery, presence and cluster
        counters) under `server`, and the `streams` subscribed here:

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

    def cluster_info(self) -> list[dict]:
        """The other machines this one is connected to, from wse: one dict
        per peer, with `address`, `instance_id` and `connected`. Empty
        without a cluster, or in a process that doesn't serve the
        WebSockets."""
        if not self.serving or not self._cluster:
            return []
        return list(self.server.cluster_info())

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
            self._executor = t.cast(ThreadPoolExecutor, _InlineExecutor())
            self.server = server
            self._owner_pid = os.getpid()
            return server

    def _new_server(self, port: int) -> t.Any:
        from wse_server import RustWSEServer

        if "handshake_details" not in (RustWSEServer.__text_signature__ or ""):
            raise RuntimeError(
                "Cable needs proper-wse >= 2.7.0, not an older one or the original "
                "wse-server (they all import as wse_server): uv add proper-wse"
            )
        options: dict[str, t.Any] = {
            "max_connections": self._max_connections,
            "handshake_details": True,
            "ping_interval": int(self.app.config.get("CABLE_PING_INTERVAL") or 3),
            **self._server_options,
        }
        options.setdefault("allowed_origins", allowed_origins(self.app.config))
        return RustWSEServer(self._host, port, **options)

    def _watch(self, limit: int, stall: float) -> None:
        """Close the connections of clients that stopped reading: more than
        `limit` bytes queued and nothing written for `stall` seconds, or ten
        times `limit` at any speed. Closed at once, without the close
        handshake, which they would never let through; `cable.js` reconnects
        and subscribes again."""
        seen: dict[str, tuple[int, float]] = {}  # conn_id -> (written, since)
        while not self._stopping.wait(min(1.0, stall / 2)):  # set before the server stops
            now = time.monotonic()
            still: dict[str, tuple[int, float]] = {}
            for conn_id, pending, written in self.server.connection_backlogs(limit):
                last = seen.get(conn_id)
                stalled = last is not None and last[0] == written and now - last[1] >= stall
                if pending >= 10 * limit or stalled:
                    logger.warning(
                        "⚠️ [cable] closed a client that stopped reading "
                        "(%d bytes waiting)", pending,
                    )
                    self.server.abort_connection(conn_id)
                elif last is not None and last[0] == written:
                    still[conn_id] = last
                else:
                    still[conn_id] = (written, now)
            seen = still

    def stop_server(self) -> None:
        """Stop serving. The drain thread goes first: it holds the server
        object while it waits for events, and `stop()` needs it alone."""
        with self._start_lock:
            server = self.server
            if server is None or not self.serving:
                return
            if isinstance(server, InMemoryServer):
                self._end_open_connections()
                self.server = None
                self._owner_pid = None
                return
            self._stopping.set()
            if self._watcher is not None:
                self._watcher.join()
                self._watcher = None
            receiver = t.cast(_ForwardedServer, self._receiver)
            receiver.shutdown()
            receiver.server_close()
            self._receiver = None
            self._draining = False
            t.cast(threading.Thread, self._drain_thread).join()
            self._end_open_connections()
            self._executor.shutdown(wait=True)
            server.stop()
            self.server = None
            self._owner_pid = None

    def _end_open_connections(self) -> None:
        """The connections still open end here: their channels'
        `unsubscribed()` runs, as it would have on a disconnect."""
        for conn in list(self._connections.values()):
            conn.closing = True
            conn.enqueue(_DISCONNECT)
        self._connections.clear()

    def _drain(self) -> None:
        server = self.server
        while self._draining and server.is_running():
            for kind, conn_id, payload in server.drain_inbound(256, 50):
                self._handle_event(kind, conn_id, payload)

    def _handle_event(self, kind: str, conn_id: str, payload: t.Any) -> None:
        """One event of the server: a connection, a message, a disconnect."""
        connections = self._connections
        if kind == "cluster_msg":
            self._control(payload)
            return
        if kind == "connect" or kind == "auth_connect":
            # `auth_connect` is wse's JWT path, which the cable doesn't use
            connections[conn_id] = WseConnection(
                self, conn_id, payload if isinstance(payload, dict) else {}
            )
            return
        conn = connections.get(conn_id)
        if conn is None:  # pragma: no cover - wse sends connect first
            return
        if kind == "msg":
            conn.enqueue(payload)
        elif kind == "raw":
            try:
                conn.enqueue(json.loads(payload))
            except ValueError:
                conn.put({"type": "error", "reason": "invalid_json"})
        elif kind == "disconnect":  # pragma: no branch - other kinds are ignored
            del connections[conn_id]
            conn.closing = True
            conn.enqueue(_DISCONNECT)

    def _control(self, payload: dict) -> None:
        """What another machine's cable told this one (`CONTROL_TOPIC`)."""
        if payload.get("topic") != CONTROL_TOPIC:
            return
        try:
            message = jsonplus.loads(payload["data"])
        except (ValueError, KeyError, TypeError):
            logger.warning("⚠️ [cable] ignored a message from the cluster that isn't JSON")
            return
        if isinstance(message, dict) and isinstance(message.get("disconnect"), dict):
            self._disconnect_local(message["disconnect"])

    # Streams

    def subscribe(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(WseConnection, channel._connection)
        key = (conn.conn_id, stream_name)
        with self._lock:
            refs = self._stream_refs.get(key, 0)
            self._stream_refs[key] = refs + 1
        if not refs:
            self.server.subscribe_connection(conn.conn_id, [stream_name])

    def unsubscribe(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(WseConnection, channel._connection)
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
        """Hand an encoded broadcast to the server, once delivery has caught up."""
        server = self.server
        if self._backpressure_bytes:
            self._wait_for_delivery(server, stream_name)
        if self._cluster:
            server.broadcast(stream_name, frame)  # here and on the other machines
        else:
            server.broadcast_local(stream_name, frame)

    def _wait_for_delivery(self, server: t.Any, stream_name: str) -> None:
        """Wait while the stream's subscribers are behind (see `__init__`)."""
        deadline = 0.0
        while True:
            count, total, _ = server.topic_backlog(stream_name)
            if not count or total <= self._backpressure_bytes * count:
                return
            now = time.monotonic()
            if not deadline:
                deadline = now + self._backpressure_timeout
            elif now >= deadline:
                return  # still behind: send it anyway, later than asked
            time.sleep(0.002)

    # Presence

    def track(self, stream_name: str, data: dict, channel: "Channel", key: t.Any = None) -> None:
        conn = t.cast(WseConnection, channel._connection)
        conn.presence_identity(key)
        self.server.subscribe_connection(conn.conn_id, [stream_name], data)

    def untrack(self, stream_name: str, channel: "Channel") -> None:
        conn = t.cast(WseConnection, channel._connection)
        if conn.presence_key is not None and not conn.closing:
            self.server.untrack_presence(conn.conn_id, [stream_name])

    def update_presence(self, channel: "Channel", data: dict) -> None:
        conn = t.cast(WseConnection, channel._connection)
        if conn.presence_key is None:
            raise ValueError("the connection is not present anywhere: track() first")
        self.server.update_presence(conn.conn_id, data)

    def presence(self, stream_name: str) -> dict[str, dict]:
        if not self.serving or not self._presence:
            return {}
        return self.server.presence(stream_name)

    def presence_stats(self, stream_name: str) -> dict[str, int]:
        if not self.serving or not self._presence:
            return {"users": 0, "connections": 0}
        stats = self.server.presence_stats(stream_name)
        return {"users": stats["num_users"], "connections": stats["num_connections"]}

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

    def disconnect(self, *, user_id: t.Any) -> None:
        super().disconnect(user_id=user_id)
        if self.serving and self._cluster:
            # The other machines' servers listen to the control topic
            self.server.broadcast(CONTROL_TOPIC, jsonplus.dumps({"disconnect": {"user_id": user_id}}))

    def _disconnect_local(self, who: dict) -> None:
        with self._lock:
            connections = list(self._users.get(who.get("user_id"), ()))
        for connection in connections:
            connection.close_threadsafe()

    # Commands, in a worker thread, one connection at a time

    def _command(self, conn: WseConnection, msg: t.Any) -> None:
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
                # One call per epoch the client saw: in a cluster, each
                # machine's broadcasts carry its own
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
            stream: {key: entry["data"] for key, entry in self.server.presence(stream).items()}
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

    def _cleanup(self, conn: WseConnection) -> None:
        self._unregister(conn)
        for channel in conn.subscriptions.values():
            try:
                channel.stop_all_streams()
                self.app._with_db(lambda ch=channel: ch._dispatch("unsubscribed"))
            except Exception:
                logger.exception("Error in %s.unsubscribed", channel.channel_name)
        conn.subscriptions.clear()
