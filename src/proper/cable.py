"""Pub/sub backends for WebSocket channels.

Manages the mapping of stream names to subscribed Channel instances.
When a message is broadcast to a stream, all channels subscribed to
that stream receive it.

Two backends are provided:

- ``Cable`` — in-process only (single worker).
- ``RedisCable`` — Redis pub/sub (multi-worker).
"""
import asyncio
import typing as t

from .helpers import jsonplus, logger


try:
    import redis
except ImportError:
    redis = None  # type: ignore

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None  # type: ignore


if t.TYPE_CHECKING:
    from .channel import Channel


__all__ = ("Cable", "RedisCable")


class Cable:
    def __init__(self) -> None:
        self._streams: dict[str, set["Channel"]] = {}

    @property
    def streams(self) -> dict[str, int]:
        """Return a dict of stream names to listener counts (for debugging)."""
        return {name: len(channels) for name, channels in self._streams.items()}

    def subscribe(self, stream_name: str, channel: "Channel") -> None:
        """Register a channel to receive broadcasts on a stream."""
        self._streams.setdefault(stream_name, set()).add(channel)
        logger.debug(
            "[cable] %s subscribed to %s", channel.channel_name, stream_name,
        )

    def unsubscribe(self, stream_name: str, channel: "Channel") -> None:
        """Remove a channel from a stream."""
        listeners = self._streams.get(stream_name)
        if not listeners:
            return
        listeners.discard(channel)
        if not listeners:
            del self._streams[stream_name]

    def unsubscribe_all(self, channel: "Channel") -> None:
        """Remove a channel from all streams it is subscribed to."""
        for stream_name in list(self._streams):
            self.unsubscribe(stream_name, channel)

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Send data to all channels subscribed to a stream."""
        self._deliver_local(stream_name, data)

    def _deliver_local(self, stream_name: str, data: t.Any) -> None:
        """Deliver data to all local channels subscribed to a stream."""
        listeners = self._streams.get(stream_name)
        if not listeners:
            return
        logger.debug(
            "[cable] broadcasting to %s (%d listeners)",
            stream_name, len(listeners),
        )
        for channel in list(listeners):
            try:
                channel.send(data)
            except Exception:
                logger.exception(
                    "[cable] error sending to %s", channel.channel_name,
                )

    async def start(self) -> None:
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
        if redis is None or aioredis is None:
            raise ImportError(
                "redis is required to use the Redis cable backend. "
                "Install it with: uv add redis"
            )
        super().__init__()
        self._url = url
        self._prefix = prefix
        self._pub_redis: "redis.Redis | None" = None
        self._sub_redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    def broadcast(self, stream_name: str, data: t.Any) -> None:
        """Publish to Redis. The listener delivers to local channels."""
        payload = jsonplus.dumps(data)
        self._get_pub_redis().publish(self._prefix + stream_name, payload)

    def _get_pub_redis(self) -> "redis.Redis":
        if self._pub_redis is None:
            self._pub_redis = redis.from_url(self._url)
        return self._pub_redis

    async def start(self) -> None:
        """Start the Redis pub/sub listener."""
        self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Background task: subscribe to Redis, deliver messages locally.

        Reconnects with exponential backoff on connection errors.
        """
        delay = 1
        while True:
            try:
                sub = aioredis.from_url(self._url)
                pubsub = sub.pubsub()
                self._sub_redis = sub
                self._pubsub = pubsub
                await pubsub.psubscribe(self._prefix + "*")
                logger.info("[cable] Redis listener connected")
                delay = 1

                async for message in pubsub.listen():
                    if message["type"] == "pmessage":
                        channel_name = message["channel"]
                        if isinstance(channel_name, bytes):
                            channel_name = channel_name.decode()
                        stream_name = channel_name[len(self._prefix):]
                        data = jsonplus.loads(message["data"])
                        self._deliver_local(stream_name, data)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning(
                    "[cable] Redis connection lost, reconnecting in %ds",
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
            finally:
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
        """Stop the listener and close all connections."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pub_redis:
            self._pub_redis.close()
            self._pub_redis = None
