"""`WseCable` on several machines, through Redis.

```python
CABLE = {
    "type": "proper.channels.RedisCable",
    "url": "redis://localhost:6379/0",
    "prefix": "myapp:cable:",
}
```

Each machine's web process serves its own WebSockets with proper-wse, as
`WseCable` does. A broadcast goes straight to the subscribers of the process
that makes it, if it serves any, and to Redis, where the web processes of the
other machines get it and hand it to theirs. Each skips what it published
itself. A process without WebSockets (a task worker, a shell) only publishes
to Redis, so there is no forwarding over HTTP. `disconnect()` goes the same
way.

Redis pub/sub carries events, not state: a process that is reconnecting to
Redis misses what was published meanwhile. Tests that run the cable from
memory (`TestClient.websocket()`) don't use Redis.
"""
import threading
import time
import typing as t
import uuid

from ..helpers import jsonplus, logger
from .wse import InMemoryServer, WseCable, _broadcast_frame


if t.TYPE_CHECKING:
    from ..app import App


# Imported on first use: an app with another cable should not pay for loading
# the library at startup.
redis: t.Any = None

# Longest the listener waits between attempts to reconnect.
MAX_RECONNECT_DELAY = 30
# How long `start_server()` waits for the listener to subscribe.
SUBSCRIBE_WAIT = 1.0


def _load_redis() -> None:
    global redis
    if redis is not None:
        return
    try:
        import redis as module
    except ImportError:
        raise ImportError(
            "redis is required to use RedisCable. Install it with: uv add redis"
        ) from None
    redis = module


class RedisCable(WseCable):
    """See the module. Takes the options of `WseCable` too."""

    # The other processes publish to Redis instead of forwarding over HTTP.
    takes_forwarded = False

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        prefix: str = "proper:cable:",
        **options: t.Any,
    ) -> None:
        _load_redis()
        super().__init__(**options)
        self._url = url
        self._prefix = prefix
        self._channel = prefix + "broadcasts"
        # Tells this process's own messages apart when they come back.
        self._origin = uuid.uuid4().hex
        self._publisher: t.Any = None
        self._publisher_lock = threading.Lock()
        self._listener: threading.Thread | None = None
        self._listening = threading.Event()  # cleared to stop the listener
        self._subscribed = threading.Event()

    def bind(self, app: "App") -> None:
        self.app = app  # nothing to forward to

    # Broadcasting

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        frame = _broadcast_frame(stream_name, data)
        if self.serving:
            self._send_frame(stream_name, frame)
            if isinstance(self.server, InMemoryServer):
                return  # a test: no other machines
        self._publish({"o": self._origin, "s": stream_name, "f": frame})

    def disconnect(self, *, user_id: t.Any) -> None:
        who = {"user_id": user_id}
        if self.serving:
            self._disconnect_local(who)
            if isinstance(self.server, InMemoryServer):
                return
        self._publish({"o": self._origin, "x": who})

    def _publish(self, message: dict) -> None:
        """Publish to the other machines. A Redis that is down loses the
        message and logs it; the page that broadcast still renders."""
        try:
            self._get_publisher().publish(self._channel, jsonplus.dumps(message))
        except redis.RedisError as error:
            logger.warning("⚠️ [cable] could not publish to Redis at %s: %s", self._url, error)

    def _get_publisher(self) -> t.Any:
        # Broadcasts come from any thread: one client, with its own pool.
        with self._publisher_lock:
            if self._publisher is None:
                self._publisher = redis.from_url(self._url)
            return self._publisher

    # Lifecycle

    def start_server(self) -> None:
        """Serve this machine's WebSockets, and deliver what the other
        machines publish. Waits a moment for the subscription, so that what is
        published right after the start isn't missed."""
        super().start_server()
        with self._start_lock:
            if self._listener is not None:
                return
            self._listening.set()
            self._subscribed.clear()
            self._listener = threading.Thread(
                target=self._listen, name="proper-cable-redis", daemon=True
            )
            self._listener.start()
        if not self._subscribed.wait(SUBSCRIBE_WAIT):
            logger.warning(
                "⚠️ [cable] not subscribed to Redis at %s yet: broadcasts from "
                "other machines arrive once it is", self._url,
            )

    def stop_server(self) -> None:
        listener = self._listener
        if listener is not None:
            self._listening.clear()
            listener.join()
            self._listener = None
        super().stop_server()
        with self._publisher_lock:
            if self._publisher is not None:
                self._publisher.close()
                self._publisher = None

    def _listen(self) -> None:
        """Subscribe to Redis and deliver what the other machines publish.

        Reconnects whenever the subscription ends. One that outlives its own
        backoff counts as healthy and resets the wait; one that dies sooner is
        flapping, so each retry waits twice as long as the last.
        """
        delay = 0
        while self._listening.is_set():
            started = time.monotonic()
            # Neither connects yet: subscribing does.
            client = redis.from_url(self._url)
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            try:
                pubsub.subscribe(self._channel)
                self._subscribed.set()
                while self._listening.is_set():
                    message = pubsub.get_message(timeout=0.2)
                    if message is not None:
                        self._receive(message["data"])
                return
            except Exception as error:
                reason = error
            finally:
                self._subscribed.clear()
                for closable in (pubsub, client):
                    try:
                        closable.close()
                    except Exception:  # pragma: no cover - closing a dead connection
                        pass
            lasted = time.monotonic() - started
            delay = 1 if lasted >= delay else min(delay * 2, MAX_RECONNECT_DELAY)
            logger.warning(
                "⚠️ [cable] Redis connection lost (%s), reconnecting in %ds", reason, delay,
            )
            deadline = time.monotonic() + delay
            while self._listening.is_set() and time.monotonic() < deadline:
                time.sleep(0.05)

    def _receive(self, raw: bytes | str) -> None:
        try:
            message = jsonplus.loads(raw)
        except ValueError:
            logger.warning("⚠️ [cable] ignored a message in Redis that isn't JSON")
            return
        if message.get("o") == self._origin:
            return  # ours, already delivered here
        if "f" in message:
            self._send_frame(message["s"], message["f"])
        elif "x" in message:
            self._disconnect_local(message["x"])
