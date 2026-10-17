"""RedisCable: Cable on several machines, through Redis. Each "machine"
here is an app with its own port, all on the test Redis."""
import logging
import socket
import time
import uuid

import pytest

from proper import App, Channel, current
from proper.channels import redis_cable
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


class WhoChannel(Channel):
    """Present in "who" as the key the test gives (a real app decides the
    key on the server, never from `params`)."""

    def subscribed(self):
        self.stream_from("who")
        if self.params.get("as"):
            self.track("who", {"name": self.params["as"]}, key=self.params["as"])

    def rename(self, data):
        self.update_presence({"name": data["name"]})


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
        app.router.channels["WhoChannel"] = WhoChannel
        made.append(app)
        if start:
            app.cable.start_server()
        return app

    EVENTS.clear()
    yield make
    for app in made:
        app.cable.stop_server()
    client = redis.from_url(redis_url)
    keys = list(client.scan_iter(f"{prefix}*"))
    if keys:
        client.delete(*keys)


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


def test_a_bad_message_doesnt_cost_the_subscription(machines, redis_url, caplog):
    one = machines()
    a = _subscribed(one)
    with caplog.at_level(logging.WARNING, logger="proper"):
        publisher = redis.from_url(redis_url)
        publisher.publish(one.cable._channel, b"[1, 2]")
        publisher.publish(one.cable._channel, b'{"o": "elsewhere", "f": "no stream"}')
        assert _wait(lambda: "could not deliver a message" in caplog.text)
    assert "isn't an object" in caplog.text
    # Right after: no reconnection, nothing lost
    machines(start=False).cable.broadcast("room:1", "still fine")
    assert a.recv_type("broadcast")["data"] == "still fine"
    assert "connection lost" not in caplog.text
    a.close()


def test_the_listener_checks_an_idle_connection(machines, monkeypatch):
    redis_cable._load_redis()
    made = []
    from_url = redis.from_url

    def spy(url, **options):
        made.append(options)
        return from_url(url, **options)

    monkeypatch.setattr(redis_cable.redis, "from_url", spy)
    one = machines()
    assert _wait(lambda: one.cable._subscribed.is_set())
    assert {"health_check_interval": redis_cable.HEALTH_CHECK_INTERVAL,
            "socket_keepalive": True} in made


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


# Presence, one list for all the machines

def _who(app, name=None):
    """A client in WhoChannel: present as `name`, or only watching."""
    client = WsClient(app.config.CABLE_PORT)
    params = {"as": name} if name else {}
    client.send({"command": "subscribe", "channel": "WhoChannel", "params": params})
    client.confirm = client.recv_type("confirm_subscription")
    return client


def _events(client, wait=0.5):
    """The presence events the client gets in `wait` seconds."""
    client.sock.settimeout(wait)
    got = []
    while (msg := client.recv()) is not None:
        if msg.get("c") == "WSE":
            got.append((msg["t"], msg["p"]["user_id"], msg["p"]["data"]))
    return got


def _next_event(client):
    while True:
        msg = client.recv()
        assert msg is not None, "closed"
        if msg.get("c") == "WSE":
            return (msg["t"], msg["p"]["user_id"], msg["p"]["data"])


def test_presence_is_one_list_for_every_machine(machines):
    one, two = machines(), machines()
    watcher = _who(two)
    ana = _who(one, "ana")  # noqa: F841 - kept open: present while it is
    assert _next_event(watcher) == ("presence_join", "ana", {"name": "ana"})
    assert two.cable.presence("who") == {"ana": {"data": {"name": "ana"}, "connections": 1}}
    assert one.cable.presence_stats("who") == {"users": 1, "connections": 1}
    # The confirmation lists who is in the streams the channel tracks, on
    # every machine
    bea = _who(two, "bea")
    assert bea.confirm["presence"] == {"who": {"ana": {"name": "ana"}, "bea": {"name": "bea"}}}


def test_a_user_on_two_machines_joins_once_and_leaves_once(machines):
    one, two = machines(), machines()
    watcher = _who(two)
    on_one = _who(one, "ana")
    assert _next_event(watcher)[:2] == ("presence_join", "ana")
    on_two = _who(two, "ana")  # the same user, on the other machine
    assert _wait(lambda: one.cable.presence("who")["ana"]["connections"] == 2)
    on_one.close()
    assert _wait(lambda: one.cable.presence("who")["ana"]["connections"] == 1)
    assert _events(watcher) == []  # still present, on the other machine
    on_two.close()
    assert _next_event(watcher)[:2] == ("presence_leave", "ana")
    assert two.cable.presence("who") == {}


def test_new_data_reaches_every_machine(machines):
    one, two = machines(), machines()
    watcher = _who(two)
    ana = _who(one, "ana")
    _next_event(watcher)
    ana.send({"command": "message", "channel": "WhoChannel", "params": {"as": "ana"},
              "action": "rename", "data": {"name": "Ana"}})
    assert _next_event(watcher) == ("presence_update", "ana", {"name": "Ana"})
    assert two.cable.presence("who")["ana"]["data"] == {"name": "Ana"}


def test_a_machine_that_dies_leaves(machines):
    one, two = machines(), machines()
    watcher = _who(two)
    ana = _who(one, "ana")  # noqa: F841 - kept open
    _next_event(watcher)
    # one dies: no more heartbeats, and its key runs out
    one.cable._beating.clear()
    one.cable._beater.join()
    one.cable._beater = None
    redis.from_url(one.cable._url).delete(one.cable._alive_key(one.cable._origin))
    two.cable._beat()  # two notices, and drops what one had
    assert _next_event(watcher) == ("presence_leave", "ana", {"name": "ana"})
    assert two.cable.presence("who") == {}
    two.cable._beat()  # once is enough: nothing left to drop
    assert _events(watcher, wait=0.2) == []


def test_the_heartbeat_keeps_running(machines, monkeypatch):
    monkeypatch.setattr(redis_cable, "ALIVE_EVERY", 0.05)
    one = machines()
    client = redis.from_url(one.cable._url)
    client.delete(one.cable._alive_key(one.cable._origin))
    assert _wait(lambda: client.exists(one.cable._alive_key(one.cable._origin)))


def test_a_machine_that_stops_takes_its_users_out(machines):
    one, two = machines(), machines()
    watcher = _who(two)
    ana = _who(one, "ana")  # noqa: F841 - kept open
    _next_event(watcher)
    one.cable.stop_server()
    assert _next_event(watcher)[:2] == ("presence_leave", "ana")
    assert two.cable.presence("who") == {}
    client = redis.from_url(one.cable._url)
    assert not client.exists(one.cable._alive_key(one.cable._origin))
    assert not client.exists(one.cable._streams_key(one.cable._origin))


def test_without_redis_presence_is_this_machines(machines, caplog):
    with caplog.at_level(logging.WARNING, logger="proper"):
        lonely = machines(url="redis://127.0.0.1:1/0")
        watcher = _who(lonely)
        ana = _who(lonely, "ana")  # noqa: F841 - kept open
        assert _next_event(watcher) == ("presence_join", "ana", {"name": "ana"})
        assert lonely.cable.presence("who") == {"ana": {"data": {"name": "ana"}, "connections": 1}}
    assert "could not share presence through Redis" in caplog.text
    assert "could not read presence from Redis" in caplog.text
    assert "could not keep presence in Redis" in caplog.text


def test_a_machine_with_presence_off_keeps_out_of_redis(machines):
    one = machines(presence=False)
    assert one.cable._beater is None
    assert one.cable.presence("who") == {}



def test_from_memory_presence_is_local(machines):
    app = machines(start=False)
    server = app.cable.serve_in_memory()
    conn_id = server.connect()
    server.client_send(conn_id, '{"command": "subscribe", "channel": "WhoChannel", '
                                '"params": {"as": "ana"}}')
    assert app.cable.presence("who") == {"ana": {"data": {"name": "ana"}, "connections": 1}}
    app.cable.stop_server()


def test_what_this_machine_left_in_redis_goes_when_it_stops(machines):
    """An entry whose leave was lost (Redis was down at that moment): the
    machine takes it out when it stops, and the others hear the leave."""
    one, two = machines(), machines()
    watcher = _who(two)
    one.cable._script("set", redis_cable._SET_PRESENCE)(
        keys=[one.cable._presence_key("who")],
        args=["ghost", one.cable._origin, '[{"name": "ghost"}, 1, 0]'],
    )
    redis.from_url(one.cable._url).sadd(one.cable._streams_key(one.cable._origin), "who")
    one.cable.stop_server()
    assert _next_event(watcher) == ("presence_leave", "ghost", {"name": "ghost"})


def test_a_dead_machine_another_is_dropping_is_skipped(machines):
    one, two = machines(), machines()
    ana = _who(one, "ana")  # noqa: F841 - kept open
    assert _wait(lambda: two.cable.presence("who"))
    one.cable._beating.clear()
    one.cable._beater.join()
    one.cable._beater = None
    client = redis.from_url(one.cable._url)
    client.delete(one.cable._alive_key(one.cable._origin))
    client.set(f"{one.cable._prefix}purging:{one.cable._origin}", "1", ex=30)  # another's
    two.cable._beat()
    assert "ana" in two.cable.presence("who")
