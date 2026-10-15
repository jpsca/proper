"""RedisCable: Cable on several machines, through Redis. Each "machine"
here is an app with its own port, all on the test Redis."""
import logging
import socket
import time
import uuid

import pytest

from proper import App, current
from .test_cable_server import (
    EVENTS,
    SECRET,
    LobbyChannel,
    RoomChannel,
    WsClient,
    _cookie,
    _free_ports,
    _wait,
)


redis = pytest.importorskip("redis")


@pytest.fixture()
def machines(redis_url):
    """Make apps that share a Redis and a prefix: each one a machine."""
    prefix = f"test-{uuid.uuid4().hex}:"
    made = []

    def make(start=True, url=redis_url, prefix=prefix, **cable):
        app = App("proper", {
            "SECRET_KEYS": [SECRET],
            "CABLE_PORT": _free_ports(),
            "CABLE": {"type": "proper.channels.RedisCable", "url": url,
                      "prefix": prefix, "host": "127.0.0.1", **cable},
        })
        current.app = app
        app.router.channels["RoomChannel"] = RoomChannel
        made.append(app)
        if start:
            app.cable.start_server()
        return app

    EVENTS.clear()
    yield make
    for app in made:
        app.cable.stop_server()


def _subscribed(app, room=1, **kwargs):
    client = WsClient(app.config.CABLE_PORT, _cookie(app), **kwargs)
    client.subscribe(room)
    return client


def _nothing_more(client, wait=0.4):
    client.sock.settimeout(wait)
    return client.recv_type("broadcast") is None


def test_a_broadcast_reaches_every_machine_once(machines):
    one, two = machines(), machines()
    a, b = _subscribed(one), _subscribed(two)
    one.cable.broadcast("room:1", "hello")
    assert a.recv_type("broadcast")["data"] == "hello"  # here, straight away
    assert b.recv_type("broadcast")["data"] == "hello"  # there, through Redis
    assert _nothing_more(a)  # its own copy from Redis is skipped
    a.close()
    b.close()


def test_a_process_without_websockets_publishes_to_redis(machines):
    one, two = machines(), machines()
    worker = machines(start=False)  # a task worker, a shell
    a, b = _subscribed(one), _subscribed(two)
    worker.cable.broadcast("room:1", "from a task")
    assert a.recv_type("broadcast")["data"] == "from a task"
    assert b.recv_type("broadcast")["data"] == "from a task"
    a.close()
    b.close()


def test_disconnect_reaches_every_machine(machines):
    one, two = machines(), machines()
    a, b = _subscribed(one), _subscribed(two)
    two.cable.disconnect(user_id=7)
    assert a.recv_type("never") is None
    assert b.recv_type("never") is None
    assert _wait(lambda: EVENTS.count(("unsubscribed", 1)) == 2)


def test_a_process_without_websockets_disconnects_through_redis(machines):
    one = machines()
    a = _subscribed(one)
    machines(start=False).cable.disconnect(user_id=7)
    assert a.recv_type("never") is None


def test_apps_with_other_prefixes_are_apart(machines):
    one = machines()
    other = machines(prefix="another-app:")
    c = _subscribed(other)
    one.cable.broadcast("room:1", "not for you")
    assert _nothing_more(c)
    c.close()


def test_the_listener_reconnects_after_losing_redis(machines, redis_url):
    one, two = machines(), machines()
    b = _subscribed(two)
    redis.from_url(redis_url).client_kill_filter(_type="pubsub")
    assert _wait(lambda: not two.cable._subscribed.is_set(), timeout=2)
    assert _wait(two.cable._subscribed.is_set, timeout=5)
    one.cable.broadcast("room:1", "back")
    assert b.recv_type("broadcast")["data"] == "back"
    b.close()


def test_without_redis_a_machine_still_serves_its_own(machines, caplog):
    with caplog.at_level(logging.WARNING, logger="proper"):
        lonely = machines(url="redis://127.0.0.1:1/0")
        a = _subscribed(lonely)
        lonely.cable.broadcast("room:1", "local")
        assert a.recv_type("broadcast")["data"] == "local"
        lonely.cable.disconnect(user_id=7)
        assert a.recv_type("never") is None
    assert "not subscribed to Redis" in caplog.text
    assert "could not publish to Redis" in caplog.text
    start = time.monotonic()
    lonely.cable.stop_server()  # the listener's retries don't hold it up
    assert time.monotonic() - start < 5


def test_messages_that_are_not_json_are_ignored(machines, redis_url, caplog):
    one = machines()
    a = _subscribed(one)
    with caplog.at_level(logging.WARNING, logger="proper"):
        publisher = redis.from_url(redis_url)
        publisher.publish(one.cable._channel, b"\xff garbage")
        publisher.publish(one.cable._channel, b'{"o": "elsewhere", "what": "unknown"}')
        assert _wait(lambda: "isn't JSON" in caplog.text)
    machines(start=False).cable.broadcast("room:1", "still fine")
    assert a.recv_type("broadcast")["data"] == "still fine"
    a.close()


def test_no_port_for_forwarded_broadcasts(machines):
    one = machines()
    with socket.socket() as s:
        s.bind(("127.0.0.1", one.config.CABLE_PORT + 1))
    assert one.cable._forward_url is None


def test_it_starts_and_stops_once(machines):
    one = machines()
    listener = one.cable._listener
    one.cable.start_server()
    assert one.cable._listener is listener
    one.cable.stop_server()
    one.cable.stop_server()
    assert one.cable._listener is None and not one.cable.serving


def test_a_server_that_fails_to_build_is_reported(machines):
    with pytest.raises(TypeError, match="bogus"):
        machines(bogus=1)


def test_a_taken_port_fails_and_leaves_nothing_behind(machines):
    port = _free_ports()
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", port))
        taken.listen()
        app = machines(start=False)
        app.config.CABLE_PORT = port
        with pytest.raises(OSError, match="in use"):
            app.cable.start_server()
    assert not app.cable.serving


def test_from_memory_nothing_goes_to_redis(machines):
    """A test's cable (`TestClient.websocket()`): broadcasts and disconnects
    stay in memory, with no other machines."""
    app = machines(start=False, url="redis://127.0.0.1:1/0")  # no Redis there
    app.router.channels["LobbyChannel"] = LobbyChannel  # takes anyone
    server = app.cable.serve_in_memory()
    conn_id = server.connect()
    server.client_send(conn_id, '{"command": "subscribe", "channel": "LobbyChannel", '
                                '"params": {"room": 1}}')
    app.cable.broadcast("room:1", "here")
    frames = []
    while not server.frames(conn_id).empty():
        frames.append(server.frames(conn_id).get_nowait())
    assert any('"data": "here"' in frame for frame in frames)
    app.cable.disconnect(user_id=7)  # nobody here: nothing happens, nothing published
    assert server.is_open(conn_id)
    app.cable.stop_server()
