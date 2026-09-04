import asyncio
import logging
import threading
import typing as t

import pytest
import redis

from proper.app import App
from proper.channels import Cable, Channel, RedisCable
from proper.errors import ConfigError
from proper.helpers import DotDict, jsonplus
from proper.tools.cable import setup as setup_cable
from proper.tools.cable import validate_config


class FakeApp:
    def __init__(self):
        self.config = DotDict({"SECRET_KEYS": ["*" * 50], "DEBUG": False})
        self.cable = Cable()


def _make_channel(app=None, params=None):
    app = t.cast(App, app or FakeApp())
    params = params or {}
    sent = []

    def send(msg):
        sent.append(msg)

    ch = Channel(app, params, _send=send)
    return ch, sent


@pytest.fixture()
def cable(redis_url):
    """Create a RedisCable connected to the test Redis."""
    return RedisCable(url=redis_url, prefix="test:cable:")


class FlakyPubSub:
    """A subscription that ends the way the caller asks it to."""

    def __init__(self, server, hold):
        self.server = server
        self.hold = hold

    async def psubscribe(self, *patterns):
        await asyncio.sleep(0)  # real psubscribe does I/O

    async def punsubscribe(self, *patterns):
        await asyncio.sleep(0)

    async def aclose(self):
        self.server.closed += 1
        await asyncio.sleep(0)

    async def listen(self):
        await asyncio.sleep(self.hold)
        if self.server.fail:
            raise ConnectionError("redis went away")
        # Ends cleanly, exactly as redis-py does once `subscribed` is False.
        return
        yield  # pragma: no cover


class FlakyRedis:
    def __init__(self, server):
        self.server = server

    def pubsub(self):
        return FlakyPubSub(self.server, self.server.next_hold())

    async def aclose(self):
        await asyncio.sleep(0)


class FlakyServer:
    """Stands in for a Redis that drops the subscription immediately.

    A real server cannot be asked to misbehave on cue, and this is the
    only way to reach the reconnect path deterministically.
    """

    def __init__(self, fail=False, holds=()):
        self.fail = fail
        # How long each successive subscription stays up before ending.
        self.holds = list(holds)
        self.attempts = 0
        self.closed = 0

    def next_hold(self):
        return self.holds.pop(0) if self.holds else 0

    def from_url(self, *args, **kwargs):
        self.attempts += 1
        return FlakyRedis(self)


@pytest.fixture()
def flaky_redis(monkeypatch):
    def install(fail=False, holds=()):
        server = FlakyServer(fail=fail, holds=holds)
        monkeypatch.setattr(
            "proper.channels.cable.aioredis", server, raising=False
        )
        return server

    return install


def _waits(caplog):
    """The delays the listener announced, in order."""
    return [
        record.getMessage().rsplit(" in ", 1)[1].removesuffix("s")
        for record in caplog.records
        if "reconnecting in" in record.getMessage()
    ]


class TestListenerReconnect:
    """`listen()` ending is a disconnect even when it does not raise."""

    async def test_a_subscription_that_ends_does_not_spin(self, flaky_redis):
        server = flaky_redis()
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        await cable.start()
        await asyncio.sleep(0.2)
        await cable.stop()

        # Without the backoff this reconnects tens of thousands of times.
        assert server.attempts <= 2, f"{server.attempts} reconnects in 0.2s"

    async def test_a_failing_connection_does_not_spin(self, flaky_redis):
        server = flaky_redis(fail=True)
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        await cable.start()
        await asyncio.sleep(0.2)
        await cable.stop()

        assert server.attempts <= 2

    async def test_each_wait_is_longer_than_the_last(self, flaky_redis, caplog):
        """Attempts land at ~0s, ~1s and ~3s. If the delay stayed at 1s
        there would already be three by 2.2s."""
        server = flaky_redis(fail=True)
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        with caplog.at_level(logging.WARNING, logger="proper"):
            await cable.start()
            await asyncio.sleep(2.2)
            await cable.stop()

        assert server.attempts == 2
        assert _waits(caplog) == ["1", "2"]

    async def test_a_healthy_connection_resets_the_wait(
        self, flaky_redis, caplog
    ):
        """One quick failure, then a subscription that outlives its own
        backoff. The wait after it goes back to 1s instead of doubling."""
        flaky_redis(fail=True, holds=[0, 1.2])
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        with caplog.at_level(logging.WARNING, logger="proper"):
            await cable.start()
            await asyncio.sleep(2.4)
            await cable.stop()

        assert _waits(caplog) == ["1", "1"]

    async def test_the_dead_connection_is_dropped_before_waiting(
        self, flaky_redis
    ):
        server = flaky_redis()
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        await cable.start()
        await asyncio.sleep(0.1)
        # Mid-backoff: nothing should still be held open.
        assert cable._pubsub is None
        assert cable._sub_redis is None
        assert server.closed >= 1

        await cable.stop()

    async def test_cancelling_closes_the_subscriber(self, flaky_redis):
        flaky_redis(fail=True)
        cable = RedisCable(url="redis://localhost:6379/0", prefix="test:")

        await cable.start()
        await asyncio.sleep(0.05)
        await cable.stop()

        assert cable._pubsub is None
        assert cable._sub_redis is None
        assert cable._listener_task is None


class TestPublisherClient:
    """The publisher is built on first use, from whichever worker thread
    happens to broadcast first."""

    def test_concurrent_broadcasts_share_one_client(self, fast_switching):
        cable = RedisCable()
        handed_out = []
        ready = threading.Barrier(8)

        def grab():
            ready.wait()
            handed_out.append(cable._get_pub_redis())

        threads = [threading.Thread(target=grab) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        try:
            assert len(handed_out) == 8
            # Every thread must have been given the client that is still
            # installed; anything else was built and thrown away.
            assert all(client is cable._pub_redis for client in handed_out)
        finally:
            for client in set(handed_out):
                client.close()

    async def test_stop_closes_the_publisher(self):
        cable = RedisCable()
        client = cable._get_pub_redis()

        await cable.stop()
        assert cable._pub_redis is None

        # Restarting is supported, so a later broadcast builds a fresh one.
        replacement = cable._get_pub_redis()
        assert replacement is not client
        replacement.close()


class TestRedisCableInit:
    def test_default_config(self):
        c = RedisCable()
        assert c._url == "redis://localhost:6379/0"
        assert c._prefix == "proper:cable:"
        assert c._streams == {}

    def test_custom_config(self):
        c = RedisCable(url="redis://redis:6380/1", prefix="myapp:")
        assert c._url == "redis://redis:6380/1"
        assert c._prefix == "myapp:"

    def test_inherits_from_cable(self):
        assert isinstance(RedisCable(), Cable)

    def test_starts_with_no_connections(self):
        c = RedisCable()
        assert c._pub_redis is None
        assert c._sub_redis is None
        assert c._listener_task is None


class TestBroadcast:
    def test_publish_reaches_redis(self, cable, redis_url):
        """Verify that broadcast() actually publishes to Redis."""
        client = redis.from_url(redis_url)
        pubsub = client.pubsub()
        pubsub.psubscribe("test:cable:*")
        # consume the psubscribe confirmation
        pubsub.get_message(timeout=1)

        cable.broadcast("chat_1", {"text": "hello"})

        msg = pubsub.get_message(timeout=2)
        assert msg is not None
        assert msg["type"] == "pmessage"
        assert msg["channel"] == b"test:cable:chat_1"
        assert jsonplus.loads(msg["data"]) == {"text": "hello"}

        pubsub.close()
        client.close()

    def test_broadcast_uses_prefix(self, cable, redis_url):
        client = redis.from_url(redis_url)
        pubsub = client.pubsub()
        pubsub.subscribe("test:cable:mystream")
        pubsub.get_message(timeout=1)

        cable.broadcast("mystream", {"x": 42})

        msg = pubsub.get_message(timeout=2) or {}
        assert msg.get("channel") == b"test:cable:mystream"

        pubsub.close()
        client.close()


class TestListener:
    async def test_listener_delivers_broadcast(self, cable):
        """Full round-trip: broadcast → Redis → listener → local channel."""
        ch, sent = _make_channel()
        cable.subscribe("room_1", ch)

        await cable.start()
        # Give the listener time to subscribe
        await asyncio.sleep(0.1)

        cable.broadcast("room_1", {"msg": "hi"})
        # Give Redis time to deliver
        await asyncio.sleep(0.2)

        await cable.stop()

        assert len(sent) == 1
        assert sent[0]["data"] == {"msg": "hi"}

    async def test_listener_delivers_to_multiple_channels(self, cable):
        ch1, sent1 = _make_channel()
        ch2, sent2 = _make_channel()
        cable.subscribe("room_1", ch1)
        cable.subscribe("room_1", ch2)

        await cable.start()
        await asyncio.sleep(0.1)

        cable.broadcast("room_1", {"msg": "all"})
        await asyncio.sleep(0.2)

        await cable.stop()

        assert len(sent1) == 1
        assert len(sent2) == 1
        assert sent1[0]["data"] == {"msg": "all"}

    async def test_listener_ignores_other_streams(self, cable):
        ch1, sent1 = _make_channel()
        ch2, sent2 = _make_channel()
        cable.subscribe("room_a", ch1)
        cable.subscribe("room_b", ch2)

        await cable.start()
        await asyncio.sleep(0.1)

        cable.broadcast("room_a", {"only": "a"})
        await asyncio.sleep(0.2)

        await cable.stop()

        assert len(sent1) == 1
        assert len(sent2) == 0

    async def test_multiple_broadcasts(self, cable):
        ch, sent = _make_channel()
        cable.subscribe("stream", ch)

        await cable.start()
        await asyncio.sleep(0.1)

        cable.broadcast("stream", {"n": 1})
        cable.broadcast("stream", {"n": 2})
        cable.broadcast("stream", {"n": 3})
        await asyncio.sleep(0.3)

        await cable.stop()

        assert len(sent) == 3
        assert [m["data"]["n"] for m in sent] == [1, 2, 3]


class TestLifecycle:
    async def test_start_creates_listener_task(self, cable):
        await cable.start()
        assert cable._listener_task is not None
        await cable.stop()

    async def test_stop_cleans_up(self, cable):
        await cable.start()
        await cable.stop()
        assert cable._listener_task is None
        assert cable._pub_redis is None

    async def test_stop_without_start_is_noop(self):
        c = RedisCable()
        await c.stop()  # should not raise

    async def test_start_stop_start_again(self, cable):
        """Can restart after stopping."""
        ch, sent = _make_channel()
        cable.subscribe("restart", ch)

        await cable.start()
        await asyncio.sleep(0.1)
        await cable.stop()

        # Start again
        await cable.start()
        await asyncio.sleep(0.1)

        cable.broadcast("restart", {"after": "restart"})
        await asyncio.sleep(0.2)

        await cable.stop()

        assert len(sent) == 1
        assert sent[0]["data"] == {"after": "restart"}


class TestSubscribeUnsubscribe:
    def test_subscribe_tracks_locally(self, cable):
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        assert cable.streams == {"chat": 1}

    def test_unsubscribe_removes_locally(self, cable):
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.unsubscribe("chat", ch)
        assert cable.streams == {}

    def test_unsubscribe_all(self, cable):
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.subscribe("notifications", ch)
        cable.unsubscribe_all(ch)
        assert cable.streams == {}

    async def test_unsubscribed_channel_stops_receiving(self, cable):
        ch, sent = _make_channel()
        cable.subscribe("room", ch)

        await cable.start()
        await asyncio.sleep(0.1)

        cable.broadcast("room", {"n": 1})
        await asyncio.sleep(0.2)

        cable.unsubscribe("room", ch)

        cable.broadcast("room", {"n": 2})
        await asyncio.sleep(0.2)

        await cable.stop()

        assert len(sent) == 1
        assert sent[0]["data"] == {"n": 1}


class TestCableTool:
    def test_default_creates_cable(self):
        app = FakeApp()
        app.config = DotDict({"SECRET_KEYS": ["*" * 50], "DEBUG": False})
        setup_cable(app)
        assert isinstance(app.cable, Cable)
        assert not isinstance(app.cable, RedisCable)

    def test_empty_dict_creates_cable(self):
        app = FakeApp()
        app.config = DotDict(
            {
                "SECRET_KEYS": ["*" * 50],
                "DEBUG": False,
                "CABLE": {},
            }
        )
        setup_cable(app)
        assert isinstance(app.cable, Cable)
        assert not isinstance(app.cable, RedisCable)

    def test_with_config_creates_redis_cable(self, redis_url):
        app = FakeApp()
        app.config = DotDict(
            {
                "SECRET_KEYS": ["*" * 50],
                "DEBUG": False,
                "CABLE": {
                    "type": "proper.channels.RedisCable",
                    "url": redis_url,
                },
            }
        )
        setup_cable(app)
        assert isinstance(app.cable, RedisCable)
        assert app.cable._url == redis_url

    def test_with_class_reference(self):
        app = FakeApp()
        app.config = DotDict(
            {
                "SECRET_KEYS": ["*" * 50],
                "DEBUG": False,
                "CABLE": {
                    "type": RedisCable,
                    "prefix": "test:",
                },
            }
        )
        setup_cable(app)
        assert isinstance(app.cable, RedisCable)
        assert app.cable._prefix == "test:"


class TestCableToolValidation:
    def test_rejects_non_dict(self):
        with pytest.raises(ConfigError, match="must be a dictionary"):
            validate_config("bad")

    def test_rejects_missing_type(self):
        with pytest.raises(ConfigError, match="must have a 'type' key"):
            validate_config({"url": "redis://localhost"})

    def test_rejects_bad_type_value(self):
        with pytest.raises(ConfigError, match="must be a string or a class"):
            validate_config({"type": 42})

    def test_accepts_valid_config(self):
        validate_config({"type": "proper.channels.RedisCable"})
        validate_config({"type": RedisCable})


class TestAppIntegration:
    def test_app_creates_cable_via_tool(self, app):
        assert isinstance(app.cable, Cable)

    async def test_lifespan_calls_start_and_stop(self, app):
        started = []
        stopped = []

        async def mock_start():
            started.append(True)

        async def mock_stop():
            stopped.append(True)

        app.cable.start = mock_start
        app.cable.stop = mock_stop

        scope = {"type": "lifespan"}
        events = asyncio.Queue()
        sent = []

        events.put_nowait({"type": "lifespan.startup"})
        events.put_nowait({"type": "lifespan.shutdown"})

        async def receive():
            return await events.get()

        async def send(msg):
            sent.append(msg)

        await app.asgi_app(scope, receive, send)

        assert started == [True]
        assert stopped == [True]
