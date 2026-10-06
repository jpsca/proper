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
CABLE = {"type": "proper.channels.wse.WseCable"}   # serves on CABLE_PORT
```

`proper run` starts the server, in its web process, before it serves the
first request (`start_server()`; call it yourself under another server).
Every other process that loads the app (the copies of `PROCESSES`, a task
worker, a shell) has no WebSockets: its broadcasts and `disconnect()`s are
forwarded to that one, signed with the app's keys, over HTTP on
`127.0.0.1:forward_port` (`CABLE_PORT + 1` unless given).

The server sends `{"type": "ping"}` to every connection each
`CABLE_PING_INTERVAL` seconds, which `cable.js` uses to notice a dead
connection, and refuses handshakes from other sites' pages (see
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
from .cable import CABLE_SALT, Cable, allowed_origins
from .channel import ActionError


if t.TYPE_CHECKING:
    from ..app import App
    from .channel import Channel


_DISCONNECT = object()
_BLOCKED_ACTIONS = (
    "subscribed", "unsubscribed",
    "send", "broadcast", "reject",
    "stream_from", "stop_stream_from", "stop_all_streams",
    "find_user",
)


def _broadcast_frame(stream_name: str, data: t.Any) -> str:
    """The frame of a broadcast: the same text for every subscriber."""
    return '{"c": "P", "type": "broadcast", "stream": %s, "data": %s}' % (
        jsonplus.dumps(stream_name), jsonplus.dumps(data)
    )


def _subscription_key(channel_name: str, params: dict) -> str:
    return f"{channel_name}:{sorted(params.items())}"


_EPOCH = re.compile(r"^[0-9a-f]{8}$")


def _client_positions(value: t.Any) -> dict[str, tuple[str, int]]:
    """The positions a `subscribe` command carries, `{stream: {"e": epoch,
    "o": offset}}`, as `{stream: (epoch, offset)}`; the malformed ones left
    out. The epoch is wse's: eight hex digits."""
    positions: dict[str, tuple[str, int]] = {}
    if not isinstance(value, dict):
        return positions
    for stream, pos in value.items():
        if not (isinstance(stream, str) and isinstance(pos, dict)):
            continue
        epoch, offset = pos.get("e"), pos.get("o")
        if (
            isinstance(epoch, str) and _EPOCH.match(epoch)
            and isinstance(offset, int) and not isinstance(offset, bool) and offset >= 0
        ):
            positions[stream] = (epoch, offset)
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


class WseConnection:
    """One WebSocket of the wse server, as the channels see it."""

    def __init__(self, cable: "WseCable", conn_id: str, cookies: str) -> None:
        self.cable = cable
        self.conn_id = conn_id
        self.request = cable.app.request_cls(
            method="GET", path=cable.app.config.get("CABLE_PATH", "/cable"),
            headers=[("cookie", cookies)] if cookies else [], app=cable.app,
        )
        self.subscriptions: dict[str, "Channel"] = {}
        self.identified = False
        self.user_id: t.Any = None
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
    cable: "WseCable"


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


class InMemoryServer:
    """The parts of `wse_server.RustWSEServer` that `WseCable` uses, in
    memory, for tests (`WseCable.serve_in_memory()`). A connection is a queue
    of the text frames written to it; `None` marks that the server closed it.
    The client side (`connect`, `client_send`, `client_close`, `frames`) is
    what `TestClient.websocket()` drives."""

    def __init__(self, cable: "WseCable") -> None:
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

    # The client side

    def connect(self, cookies: str = "") -> str:
        with self._lock:
            self._count += 1
            conn_id = f"memory-{self._count}"
            self._frames[conn_id] = queue.Queue()
            self._open.add(conn_id)
        self.cable._handle_event("connect", conn_id, cookies)
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

    # What WseCable calls

    def send(self, conn_id: str, text: str) -> None:
        if conn_id in self._open:
            self._frames[conn_id].put(text)

    def subscribe_connection(self, conn_id: str, topics: list[str]) -> None:
        with self._lock:
            for topic in topics:
                self._topics.setdefault(topic, set()).add(conn_id)

    def unsubscribe_connection(self, conn_id: str, topics: list[str]) -> None:
        with self._lock:
            for topic in topics:
                self._topics.get(topic, set()).discard(conn_id)

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
        if notify:
            self._frames[conn_id].put(None)
        return True


class WseCable(Cable):
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
        workers: int = 4,
        max_connections: int = 100_000,
        max_outbound_queue_bytes: int = 64 * 1024 * 1024,
        backpressure_bytes: int = 128 * 1024,
        backpressure_timeout: float = 1.0,
        recovery: bool = True,
        **server_options: t.Any,
    ) -> None:
        """`recovery`: keep the last broadcasts of each stream, so a client
        that reconnects gets the ones it missed (see `_subscribe`). wse's
        `recovery_buffer_size` (128 per stream), `recovery_ttl` (300 seconds)
        and `recovery_memory_budget` (256 MB) size the buffers.

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
        self._server_options = {
            "max_outbound_queue_bytes": max_outbound_queue_bytes,
            "recovery_enabled": recovery, **server_options,
        }
        self._workers = workers
        self._backpressure_bytes = backpressure_bytes
        self._backpressure_timeout = backpressure_timeout
        self._start_lock = threading.Lock()
        # The process that started the server; a forked copy of it has none.
        self._owner_pid: int | None = None
        self._receiver: _ForwardedServer | None = None
        self._stopping = threading.Event()
        self._pinger: threading.Thread | None = None
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
                raise RuntimeError("WseCable needs a port: set CABLE_PORT")
            # Bound first: a port already taken fails here, before anything runs.
            receiver = None
            if self.takes_forwarded:
                receiver = _ForwardedServer(
                    ("127.0.0.1", self._forward_port or port + 1), _ForwardedHandler
                )
                receiver.cable = self
            try:
                server = self._new_server(port)
            except BaseException:
                if receiver is not None:
                    receiver.server_close()
                raise
            server.enable_drain_mode()
            server.start()
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
            if receiver is not None:
                threading.Thread(
                    target=receiver.serve_forever, args=(0.1,), name="proper-cable-forwarded",
                    daemon=True,
                ).start()
            interval = float(self.app.config.get("CABLE_PING_INTERVAL") or 0)
            if interval > 0:
                self._pinger = threading.Thread(
                    target=self._ping, args=(interval,), name="proper-cable-ping",
                    daemon=True,
                )
                self._pinger.start()
            limit = int(self.app.config.get("CABLE_MAX_PENDING_BYTES") or 0)
            if limit > 0:
                stall = float(self.app.config.get("CABLE_STALL_TIMEOUT") or 10)
                self._watcher = threading.Thread(
                    target=self._watch, args=(limit, stall), name="proper-cable-watch",
                    daemon=True,
                )
                self._watcher.start()
            logger.info("[cable] wse-server listening on %s:%s", self._host, port)

    def serve_in_memory(self) -> "InMemoryServer":
        """Serve from memory instead of a port, for tests: no socket, no
        threads; each event and command runs in the thread that causes it,
        through the same code as the real server's. `TestClient.websocket()`
        calls it."""
        with self._start_lock:
            if isinstance(self.server, InMemoryServer):
                return self.server
            if self.serving:
                raise RuntimeError("WseCable is already serving on a port")
            server = InMemoryServer(self)
            self._executor = t.cast(ThreadPoolExecutor, _InlineExecutor())
            self.server = server
            self._owner_pid = os.getpid()
            return server

    def _new_server(self, port: int) -> t.Any:
        from wse_server import RustWSEServer

        if not all(
            hasattr(RustWSEServer, name)
            for name in ("topic_backlog", "connection_backlogs", "abort_connection")
        ):
            raise RuntimeError(
                "WseCable needs proper-wse >= 2.6.2, not an older one or the original "
                "wse-server (they all import as wse_server): uv add proper-wse"
            )
        options: dict[str, t.Any] = {"max_connections": self._max_connections, **self._server_options}
        options.setdefault("allowed_origins", allowed_origins(self.app.config))
        return RustWSEServer(self._host, port, **options)

    def _ping(self, interval: float) -> None:
        """Ping every connection: `cable.js` treats a connection that stops
        getting them as dead, and reconnects."""
        while not self._stopping.wait(interval):  # set before the server stops
            self.server.broadcast_all('{"type": "ping", "message": %d}' % int(time.time()))

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
            for thread in (self._pinger, self._watcher):
                if thread is not None:
                    thread.join()
            self._pinger = self._watcher = None
            if self._receiver is not None:
                self._receiver.shutdown()
                self._receiver.server_close()
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
        if kind == "connect" or kind == "auth_connect":
            connections[conn_id] = WseConnection(
                self, conn_id, payload if kind == "connect" else ""
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
                epoch, offset = positions[stream]
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
        conn.put({**confirm, "streams": streams, "positions": current, "recovered": recovered})

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
