import asyncio
import threading
import time
import typing as t
from collections import deque

from ..channels.cable import origin_allowed
from ..helpers import jsonplus, logger


if t.TYPE_CHECKING:
    from ..app import App
    from ..channels import Cable, Channel
    from ..router import Router
    from .request import Request

# RSGI WebSocket message kinds.
WS_CLOSE = 0
WS_BYTES = 1
WS_TEXT = 2

# Close codes the server uses (RFC 6455).
CLOSE_NORMAL = 1000
CLOSE_TRY_AGAIN_LATER = 1013

# How long a closing connection waits for what is already queued to reach
# the client, before giving up on it.
DRAIN_TIMEOUT = 5.0

_BLOCKED_ACTIONS = (
    "subscribed", "unsubscribed",
    "send", "broadcast", "reject",
    "stream_from", "stop_stream_from", "stop_all_streams",
)


def _subscription_key(channel_name: str, params: dict) -> str:
    sorted_params = sorted(params.items())
    return f"{channel_name}:{sorted_params}"


class _LoopInbox:
    """Messages for the connections of one event loop, put there by other
    threads.

    A broadcast made from a worker thread reaches every subscriber of the
    stream. Waking the loop once per subscriber is a write to its self-pipe
    each, so the messages of a burst are collected here and the loop is woken
    once to hand them all out.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._items: list[tuple["Connection", t.Any]] = []
        self._lock = threading.Lock()
        self._scheduled = False

    def put(self, connection: "Connection", msg: t.Any) -> None:
        with self._lock:
            self._items.append((connection, msg))
            if self._scheduled:
                return
            self._scheduled = True
        try:
            self.loop.call_soon_threadsafe(self._drain)
        except RuntimeError:
            # The loop is closed: its connections are gone.
            pass

    def _drain(self) -> None:
        with self._lock:
            items, self._items = self._items, []
            self._scheduled = False
        for connection, msg in items:
            connection.put(msg)


_inboxes: dict[asyncio.AbstractEventLoop, _LoopInbox] = {}
_inboxes_lock = threading.Lock()


def _inbox_for(loop: asyncio.AbstractEventLoop) -> _LoopInbox:
    inbox = _inboxes.get(loop)
    if inbox is None:
        with _inboxes_lock:
            inbox = _inboxes.get(loop)
            if inbox is None:
                inbox = _inboxes[loop] = _LoopInbox(loop)
    return inbox


class Connection:
    """One WebSocket: its channels, its outbox, and who is on the other end.

    Everything going out to the client passes through the outbox, drained by
    one task, which is what keeps the messages in the order they were sent.
    A message is a dict, a `Message` (a dict that carries its own JSON: the
    messages of a broadcast are encoded once for all their subscribers), or
    a string of JSON.
    """

    def __init__(
        self,
        cable: "Cable",
        protocol: t.Any,
        transport: t.Any,
        request: "Request",
        *,
        max_pending: int = 0,
        stall_timeout: float = 10.0,
    ) -> None:
        self.cable = cable
        self.protocol = protocol
        self.transport = transport
        self.request = request
        self.loop = asyncio.get_running_loop()
        self.subscriptions: dict[str, "Channel"] = {}
        self.max_pending = max_pending
        self.stall_timeout = stall_timeout
        # Who the connection belongs to, resolved from its cookie by the
        # first channel that authenticates, and shared by all the others.
        self.identified = False
        self.user_id: t.Any = None
        self.close_code: int | None = None
        self._outbox: deque = deque()
        self._wakeup = asyncio.Event()
        self._closing = asyncio.Event()
        self._thread_id = threading.get_ident()
        # When the writer last got a message through (or had nothing to send).
        self._progress_at = self.loop.time()

    # Sending

    def put(self, msg: t.Any) -> None:
        """Queue a message for the client. Call it from the loop thread."""
        if self._closing.is_set():
            return
        if self.max_pending and len(self._outbox) >= self.max_pending and self._stalled():
            logger.warning(
                "⚠️ [cable] closing a connection that is not reading:"
                " %d messages waiting for it", len(self._outbox),
            )
            self.close(CLOSE_TRY_AGAIN_LATER)
            return
        if not self._outbox:
            self._progress_at = self.loop.time()
        self._outbox.append(msg)
        self._wakeup.set()

    def _stalled(self) -> bool:
        """A long queue alone does not make a client slow: a busy server
        falls behind with every client at once. A client is not reading when
        its queue is long and nothing got through to it for `stall_timeout`
        seconds, or when its queue is ten times the limit regardless."""
        if len(self._outbox) >= self.max_pending * 10:
            return True
        return self.loop.time() - self._progress_at > self.stall_timeout

    def put_threadsafe(self, msg: t.Any) -> None:
        """Queue a message for the client, from any thread."""
        if threading.get_ident() == self._thread_id:
            self.put(msg)
        else:
            _inbox_for(self.loop).put(self, msg)

    async def write(self) -> None:
        """Send what is queued, in order, until the connection closes."""
        outbox = self._outbox
        while True:
            if not outbox:
                if self._closing.is_set():
                    return
                self._wakeup.clear()
                await self._wakeup.wait()
                continue
            msg = outbox.popleft()
            if isinstance(msg, str):
                text = msg
            else:
                # A `Message` of a broadcast comes encoded already.
                text = getattr(msg, "json", None) or jsonplus.dumps(msg)
            try:
                await self.transport.send_str(text)
                self._progress_at = self.loop.time()
            except Exception:
                # The connection is gone. The receive loop sees the
                # disconnect and takes care of the cleanup.
                logger.exception("[cable] could not send to the client")
                self.close()
                return

    # Closing

    def close(self, code: int = CLOSE_NORMAL) -> None:
        """Close the connection from the server side. Call it from the loop
        thread; `close_threadsafe` from any other."""
        if self._closing.is_set():
            return
        self.close_code = code
        self._closing.set()
        self._wakeup.set()

    def close_threadsafe(self, code: int = CLOSE_NORMAL) -> None:
        if threading.get_ident() == self._thread_id:
            self.close(code)
        else:
            try:
                self.loop.call_soon_threadsafe(self.close, code)
            except RuntimeError:
                pass

    @property
    def closing(self) -> bool:
        return self._closing.is_set()

    async def wait_closing(self) -> None:
        await self._closing.wait()

    # Identity

    def identify(self, user_id: t.Any) -> None:
        self.identified = True
        self.user_id = user_id
        if user_id is not None:
            self.cable._register(self)


class AppWs:
    """A Mixin for WebSocket support in Proper apps
    """
    config: dict
    router: "Router"
    cable: "Cable"

    max_threads: int

    if t.TYPE_CHECKING:
        def _with_db(self, work, *, on_error=None) -> None: ...

        async def _run_in_worker(self, func, *args) -> t.Any: ...

        def _request_from_scope(self, scope) -> "Request": ...

    async def _receive_broadcast(self: "App", scope, protocol) -> None:
        """What a process without WebSockets forwards to this one, as a
        `POST` to `CABLE_PATH`: a token signed with the app's keys, carrying
        a broadcast (`stream` and `data`), several (`batch`), or the user
        whose connections to close (`disconnect`). Anything else gets a 403;
        behind a proxy this path is reachable from outside."""
        token = (await protocol()).decode("utf-8", "replace")
        valid = self.cable.receive_forwarded(token, self.loads)
        protocol.response_empty(204 if valid else 403, [])

    async def _handle_websocket(self, scope, protocol) -> None:
        cable_path = self.config.get("CABLE_PATH", "/cable")
        # A cable with its own WebSocket server (WseCable) is the only one
        # its broadcasts reach: one opened here would never get them.
        if scope.path != cable_path or getattr(self.cable, "serves_websockets", False):
            # Before the handshake is accepted this is still HTTP, so the
            # refusal is an HTTP status, not a WebSocket close code.
            protocol.close(404)
            return
        if not origin_allowed(scope.headers.get("origin"), scope.headers.get("host", ""), self.config):
            logger.warning(
                "⚠️ [cable] refused a WebSocket from origin %s", scope.headers.get("origin"),
            )
            protocol.close(403)
            return

        transport = await protocol.accept()
        # The handshake's headers and cookies, for channels to authenticate
        # the connection with.
        request = self._request_from_scope(scope)
        conn = Connection(
            self.cable,
            protocol,
            transport,
            request,
            max_pending=int(self.config.get("CABLE_MAX_PENDING") or 0),
            stall_timeout=float(self.config.get("CABLE_STALL_TIMEOUT") or 10),
        )
        writer_task = asyncio.create_task(conn.write())
        self._start_pinger(conn)
        closing = asyncio.ensure_future(conn.wait_closing())

        try:
            while True:
                receiving = asyncio.ensure_future(transport.receive())
                done, _ = await asyncio.wait(
                    (receiving, closing), return_when=asyncio.FIRST_COMPLETED
                )
                if receiving not in done:
                    # Closed by the server: a remote disconnect, or a client
                    # that does not keep up.
                    receiving.cancel()
                    break
                try:
                    message = receiving.result()
                except Exception:
                    # The connection dropped without a close frame.
                    break
                if message.kind == WS_CLOSE:
                    break
                if message.kind != WS_TEXT:
                    continue
                if message.data:
                    await self._ws_command(conn, message.data)
        finally:
            closing.cancel()
            await self._ws_cleanup(conn, writer_task)

    async def _ws_command(self, conn: Connection, text: str) -> None:
        try:
            msg = jsonplus.loads(text)
        except Exception:
            conn.put({"type": "error", "reason": "invalid_json"})
            return

        command = msg.get("command")
        channel_name = msg.get("channel", "")
        params = msg.get("params") or {}
        sub_key = _subscription_key(channel_name, params)

        if command == "subscribe":
            await self._ws_subscribe(conn, channel_name, params, sub_key)
        elif command == "unsubscribe":
            await self._ws_unsubscribe(conn, sub_key)
        elif command == "message":
            await self._ws_message(conn, msg, sub_key)
        else:
            conn.put({"type": "error", "reason": "unknown_command"})

    async def _ws_cleanup(self, conn: Connection, writer_task: asyncio.Task) -> None:
        self.cable._unregister(conn)
        for channel in conn.subscriptions.values():
            try:
                channel.stop_all_streams()
                await self._run_in_worker(
                    self._with_db,
                    lambda ch=channel: ch._dispatch("unsubscribed"),
                )
            except Exception:
                logger.exception(
                    "Error in %s.unsubscribed", channel.channel_name,
                )
        conn.subscriptions.clear()
        # Let whatever is already queued reach the client before closing,
        # but not for longer than `DRAIN_TIMEOUT`: a client that stopped
        # reading would keep this connection open forever.
        if conn.close_code is not None:
            conn.protocol.close(conn.close_code)
        conn.close(conn.close_code or CLOSE_NORMAL)
        try:
            await asyncio.wait_for(writer_task, timeout=DRAIN_TIMEOUT)
        except (TimeoutError, asyncio.CancelledError):
            pass
        finally:
            writer_task.cancel()

    def _start_pinger(self, conn: Connection) -> None:
        """Ping every connection of this loop each `CABLE_PING_INTERVAL`
        seconds, with one timer per loop rather than one per connection.

        The pings let a client notice a dead connection (a laptop that
        slept, a proxy that dropped it) and reconnect, and they make the
        server write to every socket, which is how it finds out about the
        ones whose client vanished.
        """
        interval = float(self.config.get("CABLE_PING_INTERVAL") or 0)
        if interval <= 0:
            return
        pingers = self.__dict__.setdefault("_ws_pingers", {})
        loop = conn.loop
        connections = pingers.get(loop)
        if connections is None:
            connections = pingers[loop] = set()

            async def ping_forever() -> None:
                while True:
                    await asyncio.sleep(interval)
                    frame = '{"type": "ping", "message": %d}' % int(time.time())
                    for each in list(connections):
                        if each.closing:
                            connections.discard(each)
                        else:
                            each.put(frame)

            task = loop.create_task(ping_forever())
            # Keep a reference, or the task may be garbage collected.
            self.__dict__.setdefault("_ws_pinger_tasks", set()).add(task)
        connections.add(conn)

    async def _ws_subscribe(
        self,
        conn: Connection,
        channel_name: str,
        params: dict,
        sub_key: str,
    ) -> None:
        if sub_key in conn.subscriptions:
            # Already subscribed (two elements of a page asking for the same
            # thing, or a new one connected before the old one left): confirm
            # again, without a second channel on the same streams.
            conn.put({
                "type": "confirm_subscription",
                "channel": channel_name,
                "params": params,
            })
            return

        channel_cls = self.router.channels.get(channel_name)
        if not channel_cls:
            conn.put({
                "type": "reject_subscription",
                "channel": channel_name,
                "params": params,
                "reason": "unknown_channel",
            })
            return

        # Until the subscription is accepted, messages are held back rather
        # than sent: `subscribed()` may still reject, and a rejected channel
        # must not reach the client. `pending` becomes `None` once that is
        # settled, and everything goes straight to the outbox from then on.
        # The lock is what makes the handover atomic for the worker thread
        # `subscribed()` runs in, and for any thread broadcasting to a stream
        # it just opened.
        pending: list | None = []
        handover = threading.Lock()

        def send(msg):
            with handover:
                if pending is not None:
                    pending.append(msg)
                    return
            conn.put_threadsafe(msg)

        channel = channel_cls(
            t.cast("App", self),
            params,
            request=conn.request,
            _send=send,
            _connection=conn,
        )
        await self._run_in_worker(
            self._with_db,
            lambda: channel._dispatch("subscribed"),
        )

        if channel._rejected:
            # `subscribed()` may have opened streams before deciding to
            # reject. Nothing else would ever close them: the channel is
            # not in `subscriptions`, so the cleanup on disconnect misses it.
            channel.stop_all_streams()
            conn.put({
                "type": "reject_subscription",
                "channel": channel_name,
                "params": params,
            })
            return

        conn.subscriptions[sub_key] = channel

        # Release whatever `subscribed()` sent, and let later messages
        # through. Both happen under the lock so nothing overtakes them.
        with handover:
            for msg in pending:
                conn.put(msg)
            pending = None

        conn.put({
            "type": "confirm_subscription",
            "channel": channel_name,
            "params": params,
        })

    async def _ws_unsubscribe(self, conn: Connection, sub_key: str) -> None:
        channel = conn.subscriptions.pop(sub_key, None)
        if channel:
            channel.stop_all_streams()
            await self._run_in_worker(
                self._with_db,
                lambda: channel._dispatch("unsubscribed"),
            )

    async def _ws_message(self, conn: Connection, msg: dict, sub_key: str) -> None:
        channel = conn.subscriptions.get(sub_key)
        if not channel:
            conn.put({"type": "error", "reason": "not_subscribed"})
            return

        action = msg.get("action", "")
        if not action or action.startswith("_") or action in _BLOCKED_ACTIONS:
            conn.put({"type": "error", "reason": "invalid_action"})
            return

        if not hasattr(channel, action) or not callable(getattr(channel, action)):
            conn.put({"type": "error", "reason": "unknown_action"})
            return

        data = msg.get("data") or {}
        await self._run_in_worker(
            self._with_db,
            lambda: channel._dispatch(action, data),
        )
