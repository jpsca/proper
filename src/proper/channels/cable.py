"""Pub/sub backends for WebSocket channels.

Manages the mapping of stream names to subscribed Channel instances.
When a message is broadcast to a stream, all channels subscribed to
that stream receive it.

Two backends are provided:

- `Cable` - in-process. Enough for one worker process, or for any number of
  worker threads sharing the process. When the WebSockets live in their own
  process (`CABLE_PORT`), broadcasts made anywhere else are forwarded to it
  over the loopback, signed with the app's secret keys.
- `RedisCable` - Redis pub/sub, for several worker processes on one or more
  machines.
"""
import asyncio
import http.client
import threading
import typing as t
from urllib.parse import urlsplit

from ..helpers import jsonplus, logger


# Imported on first use: an app with the in-process cable should not pay
# for loading the library at startup.
redis: t.Any = None
aioredis: t.Any = None


def _load_redis() -> None:
    global redis, aioredis
    try:
        if redis is None:
            import redis as module

            redis = module
        if aioredis is None:
            import redis.asyncio as async_module

            aioredis = async_module
    except ImportError:
        raise ImportError(
            "redis is required to use the Redis cable backend. "
            "Install it with: uv add redis"
        ) from None


if t.TYPE_CHECKING:
    from collections.abc import Callable

    from .channel import Channel


__all__ = ("Cable", "RedisCable", "CABLE_SALT")

# Longest the Redis listener waits between attempts to reconnect.
MAX_RECONNECT_DELAY = 30

# Salt of the signature on broadcasts forwarded to the cable process.
CABLE_SALT = "cable-broadcast"
# How long such a broadcast stays valid, in seconds. Loopback is instant;
# this only bounds a replay.
FORWARD_MAX_AGE = 30
FORWARD_TIMEOUT = 2.0


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
        """Remove a channel from all streams it is subscribed to."""
        with self._lock:
            for stream_name in list(self._streams):
                self.unsubscribe(stream_name, channel)

    def forward_to(self, url: str, sign: "Callable[[t.Any], str]") -> None:
        """Send the broadcasts of any process that is not serving the
        WebSockets to `url`, the cable process's `CABLE_PATH`, signed with
        `sign`."""
        self._forward_url = url
        self._sign = sign

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Send data to all channels subscribed to a stream."""
        if self._forward_url and not self._started:
            self._forward(stream_name, data)
        else:
            self._deliver_local(stream_name, data)

    def _forward(self, stream_name: str, data: t.Any) -> None:
        """POST the broadcast to the cable process. A cable that is down
        loses the message and logs it; the page that broadcast still
        renders."""
        assert self._forward_url and self._sign
        token = self._sign({"stream": stream_name, "data": data})
        url = urlsplit(self._forward_url)
        try:
            conn = http.client.HTTPConnection(
                url.hostname or "127.0.0.1", url.port, timeout=FORWARD_TIMEOUT
            )
            try:
                conn.request(
                    "POST", url.path, body=token.encode(),
                    headers={"Content-Type": "text/plain"},
                )
                status = conn.getresponse().status
            finally:
                conn.close()
        except OSError as error:
            logger.warning(
                "[cable] could not reach the cable process at %s: %s",
                self._forward_url, error,
            )
            return
        if status != 204:
            logger.warning(
                "[cable] the cable process at %s refused a broadcast: HTTP %s",
                self._forward_url, status,
            )

    def _deliver_local(self, stream_name: str, data: t.Any) -> None:
        """Deliver data to all local channels subscribed to a stream."""
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
        for channel in listeners:
            try:
                channel.send(data)
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


class RedisCable(Cable):
    """Redis-backed pub/sub for multi-process deployments.

    Broadcasts are published to Redis and received by a background listener
    in each process, which delivers them to local channels.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        prefix: str = "proper:cable:",
    ) -> None:
        _load_redis()
        super().__init__()
        self._url = url
        self._prefix = prefix
        self._pub_redis: "redis.Redis | None" = None
        # Broadcasts reach here from any worker thread. Without this, several
        # threads race to build the publisher and every connection pool but
        # the last one is thrown away - and `stop()` only ever closes the
        # one it happens to find.
        self._pub_lock = threading.Lock()
        self._sub_redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        # On free-threaded Python the server runs its workers as threads of
        # one process, each with its own event loop, and every one of them
        # calls `start()` and `stop()` on this same cable. One listener per
        # process is enough, and any more would deliver each message once
        # per worker. So the first `start()` owns the listener, the others
        # only count themselves in, and the publisher closes with the last
        # `stop()`.
        self._life_lock = threading.Lock()
        self._listener_loop: asyncio.AbstractEventLoop | None = None
        self._starts = 0

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Publish to Redis. The listener delivers to local channels."""
        payload = jsonplus.dumps(data)
        self._get_pub_redis().publish(self._prefix + stream_name, payload)

    def _get_pub_redis(self) -> "redis.Redis":
        with self._pub_lock:
            if self._pub_redis is None:
                self._pub_redis = redis.from_url(self._url)
            return self._pub_redis

    async def start(self) -> None:
        """Start the Redis pub/sub listener, once per process."""
        with self._life_lock:
            self._starts += 1
            if self._listener_task is not None:
                return
            self._listener_loop = asyncio.get_running_loop()
            self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Background task: subscribe to Redis, deliver messages locally.

        Reconnects whenever the subscription ends, whether it broke or
        simply finished. A subscription that outlives its own backoff
        counts as healthy and resets the wait; one that dies sooner than
        that is flapping, so each retry waits twice as long as the last.
        """
        loop = asyncio.get_running_loop()
        delay = 0
        try:
            while True:
                started = loop.time()
                try:
                    sub = aioredis.from_url(self._url)
                    pubsub = sub.pubsub()
                    self._sub_redis = sub
                    self._pubsub = pubsub
                    await pubsub.psubscribe(self._prefix + "*")
                    logger.info("[cable] Redis listener connected")

                    async for message in pubsub.listen():
                        if message["type"] == "pmessage":
                            channel_name = message["channel"]
                            if isinstance(channel_name, bytes):
                                channel_name = channel_name.decode()
                            stream_name = channel_name[len(self._prefix):]
                            data = jsonplus.loads(message["data"])
                            self._deliver_local(stream_name, data)

                    # `listen()` returned instead of raising: the
                    # subscription is gone, which is not an error but is
                    # still a disconnect. Wait before trying again - a
                    # server that keeps dropping it would otherwise have
                    # us reconnecting in a tight loop.
                    reason = "subscription ended"
                except Exception:
                    reason = "connection lost"

                lasted = loop.time() - started
                delay = (
                    1 if lasted >= delay
                    else min(delay * 2, MAX_RECONNECT_DELAY)
                )
                # Let go of the dead connection before waiting, not after.
                await self._close_subscriber()
                logger.warning(
                    "[cable] Redis %s, reconnecting in %ds", reason, delay,
                )
                await asyncio.sleep(delay)
        finally:
            # Cancellation lands here too: `stop()` cancels this task and
            # `CancelledError` is not an `Exception`, so it passes straight
            # through the loop above.
            await self._close_subscriber()

    async def _close_subscriber(self) -> None:
        if self._pubsub:
            try:
                await self._pubsub.punsubscribe()
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        if self._sub_redis:
            try:
                await self._sub_redis.aclose()
            except Exception:
                pass
            self._sub_redis = None

    async def stop(self) -> None:
        """Stop the listener and close all connections.

        The listener can only be stopped from the loop that started it, so
        a `stop()` from any other worker just counts itself out. The
        publisher is shared by all workers and closes with the last one.
        """
        with self._life_lock:
            self._starts = max(0, self._starts - 1)
            last = self._starts == 0
            task = self._listener_task
            if task is not None and self._listener_loop is asyncio.get_running_loop():
                self._listener_task = None
                self._listener_loop = None
            else:
                task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if last:
            with self._pub_lock:
                if self._pub_redis:
                    self._pub_redis.close()
                    self._pub_redis = None
