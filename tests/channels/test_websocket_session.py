"""`TestClient.websocket()`: the same test, whichever cable the app uses."""
import asyncio

import pytest

from proper import App, Channel, current
from proper.test_client import TestClient


SECRET = "*" * 50
EVENTS: list = []


class FakeUser:
    def __init__(self, id):
        self.id = id


class FakeSession:
    def __init__(self, user):
        self.user = user
        self.user_id = user.id

    def touch(self):
        pass


class FakeSessionModel:
    @classmethod
    def find_by_token(cls, token):
        return FakeSession(FakeUser(7)) if token == "good" else None


class RoomChannel(Channel):
    Session = FakeSessionModel

    def find_user(self, user_id):
        return FakeUser(user_id)

    def subscribed(self):
        if self.params.get("room") == "private" and not self.authenticated:
            return self.reject()
        EVENTS.append(("subscribed", self.params["room"]))
        self.stream_from(f"room:{self.params['room']}")
        if self.authenticated:
            self.send({"hello": current.user.id})

    def unsubscribed(self):
        EVENTS.append(("unsubscribed", self.params["room"]))

    def speak(self, data):
        self.broadcast(f"room:{self.params['room']}", {"said": data["text"]})


CABLES = {
    "Cable": {"type": "proper.channels.Cable"},
}


@pytest.fixture(params=list(CABLES))
def client(request):
    app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": CABLES[request.param]})
    current.app = app
    app.router.channels["RoomChannel"] = RoomChannel
    EVENTS.clear()
    yield TestClient(app)
    if hasattr(app.cable, "stop_server"):
        app.cable.stop_server()


def _signed_in(client):
    client.default_headers["cookie"] = "_auth=" + client.app.dumps("good", salt="auth cookie")
    return client


def _data(msg):
    """What a broadcast carries: a `broadcast` frame, named by its stream."""
    assert msg["type"] == "broadcast", msg
    return msg["data"]


async def test_subscribe_returns_the_confirmation(client):
    ws = client.websocket()
    task = await ws.connect()
    confirm = await ws.subscribe("RoomChannel", room="lobby")
    assert confirm["type"] == "confirm_subscription"
    assert confirm["params"] == {"room": "lobby"}
    await ws.close()
    await task


async def test_actions_and_broadcasts(client):
    a, b = client.websocket(), client.websocket()
    tasks = [await a.connect(), await b.connect()]
    await a.subscribe("RoomChannel", room="lobby")
    await b.subscribe("RoomChannel", room="lobby")

    await a.send_action("RoomChannel", "speak", {"text": "hi"}, room="lobby")
    assert _data(await a.receive()) == {"said": "hi"}
    assert _data(await b.receive()) == {"said": "hi"}

    client.app.cable.broadcast("room:lobby", "from a controller")
    assert _data(await b.receive()) == "from a controller"
    await a.close()
    await b.close()
    await asyncio.gather(*tasks)


async def test_the_signed_in_user_reaches_the_channel(client):
    ws = _signed_in(client).websocket()
    task = await ws.connect()
    hello = await ws.subscribe("RoomChannel", room="private")
    assert hello["type"] == "message"
    assert hello["data"] == {"hello": 7}
    assert (await ws.receive())["type"] == "confirm_subscription"
    await ws.close()
    await task


async def test_an_anonymous_client_is_rejected(client):
    ws = client.websocket()
    task = await ws.connect()
    assert (await ws.subscribe("RoomChannel", room="private"))["type"] == "reject_subscription"
    await ws.close()
    await task


async def test_closing_runs_unsubscribed_before_the_task_ends(client):
    ws = client.websocket()
    task = await ws.connect()
    await ws.subscribe("RoomChannel", room="lobby")
    await ws.close()
    await task
    assert EVENTS == [("subscribed", "lobby"), ("unsubscribed", "lobby")]


async def test_a_disconnect_from_the_server_ends_the_session(client):
    ws = _signed_in(client).websocket()
    task = await ws.connect()
    await ws.subscribe("RoomChannel", room="lobby")
    await ws.receive()  # the confirmation, after the hello
    client.app.cable.disconnect(user_id=7)
    assert (await ws.receive_raw())["type"] == "close"
    await asyncio.wait_for(task, timeout=2)
    assert ("unsubscribed", "lobby") in EVENTS


async def test_protocol_errors(client):
    ws = client.websocket()
    task = await ws.connect()
    ws.client_send_text("not json")
    assert (await ws.receive()) == {"type": "error", "reason": "invalid_json"}
    await ws.close()
    await task


async def test_receive_times_out_when_nothing_comes(client):
    ws = client.websocket()
    task = await ws.connect()
    with pytest.raises(TimeoutError):
        await ws.receive(timeout=0.05)
    await ws.close()
    await task


async def test_the_handshake_is_the_first_raw_event(client):
    ws = client.websocket()
    task = await ws.connect()
    assert await ws.receive_raw() == {"type": "accept"}
    assert (await ws.subscribe("RoomChannel", room="lobby"))["type"] == "confirm_subscription"
    await ws.close()
    await task


async def test_an_app_without_websockets_says_so():
    app = App("proper", {"SECRET_KEYS": [SECRET]})
    current.app = app
    with pytest.raises(RuntimeError, match="serves no WebSockets"):
        await TestClient(app).websocket().connect()


class TestInMemoryServer:
    def _cable(self):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": CABLES["Cable"]})
        current.app = app
        app.router.channels["RoomChannel"] = RoomChannel
        EVENTS.clear()
        return app.cable

    def test_it_is_started_once(self):
        cable = self._cable()
        assert cable.serve_in_memory() is cable.serve_in_memory()
        assert cable.serving

    def test_stopping_ends_the_open_connections(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        server.client_send(conn_id, '{"command": "subscribe", "channel": "RoomChannel",'
                                    ' "params": {"room": "lobby"}}')
        cable.stop_server()
        assert not cable.serving
        assert EVENTS == [("subscribed", "lobby"), ("unsubscribed", "lobby")]

    def test_unsubscribing_stops_the_broadcasts(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        sub = '"channel": "RoomChannel", "params": {"room": "lobby"}'
        server.client_send(conn_id, '{"command": "subscribe", %s}' % sub)
        server.client_send(conn_id, '{"command": "unsubscribe", %s}' % sub)
        frames = server.frames(conn_id)
        while not frames.empty():
            frames.get_nowait()
        cable.broadcast("room:lobby", "gone")
        assert frames.empty()
        assert EVENTS == [("subscribed", "lobby"), ("unsubscribed", "lobby")]

    def test_disconnecting_twice_closes_once(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        server.disconnect(conn_id)
        server.disconnect(conn_id)
        server.send(conn_id, "too late")  # a closed connection gets nothing
        frames = server.frames(conn_id)
        assert frames.get_nowait() is None
        assert frames.empty()

    def test_a_command_that_comes_while_one_runs_waits_its_turn(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn = cable._connections[server.connect()]
        order = []

        def command(connection, msg):
            order.append(("start", msg))
            if msg == 1:
                conn.enqueue(2)  # runs after this one ends
            order.append(("end", msg))

        cable._command = command
        conn.enqueue(1)
        assert order == [("start", 1), ("end", 1), ("start", 2), ("end", 2)]

    def test_leaving_a_stream_never_joined_does_nothing(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        server.unsubscribe_connection(conn_id, ["never"])
        assert server.is_open(conn_id)

    def test_nothing_is_written_to_a_closed_connection(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        server.client_close(conn_id)
        server._write(conn_id, "late")  # a broadcast that raced the close
        assert server.frames(conn_id).empty()

    def test_a_stream_without_broadcasts_for_a_while_loses_its_buffer(self):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {
            "type": "proper.channels.Cable", "recovery_ttl": 0,
        }})
        server = app.cable.serve_in_memory()
        server.broadcast_local("old", '{"n": 1}')
        assert "old" in server._buffers
        server.broadcast_local("new", '{"n": 1}')  # within a second: no purge yet
        assert "old" in server._buffers
        server._next_purge = 0
        server.broadcast_local("new", '{"n": 2}')
        assert set(server._buffers) == {"new"}

    def _memory_server(self, **cable):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {
            "type": "proper.channels.Cable", **cable,
        }})
        return app.cable.serve_in_memory()

    def test_past_the_memory_budget_the_oldest_streams_go(self):
        server = self._memory_server(recovery_memory_budget=1000)
        frame = '{"data": "%s"}' % ("x" * 200)
        for topic in ("a", "b", "c"):
            server.broadcast_local(topic, frame)
        server.broadcast_local("a", frame)  # "a" is the newest now
        assert set(server._buffers) == {"a", "b", "c"}
        server.broadcast_local("d", frame)  # past 1000: "b" broadcast last the longest ago
        assert list(server._buffers) == ["c", "a", "d"]
        assert server._buffers_size == sum(b.size for b in server._buffers.values())
        assert server._buffers_size <= 1000

    def test_a_stream_alone_past_the_budget_keeps_its_buffer(self):
        server = self._memory_server(recovery_memory_budget=10)
        server.broadcast_local("big", '{"data": "%s"}' % ("x" * 100))
        assert list(server._buffers) == ["big"]

    def test_the_size_follows_the_frames_a_buffer_keeps(self):
        server = self._memory_server(recovery_buffer_size=2, recovery_ttl=0)
        for n in range(5):
            server.broadcast_local("a", '{"n": %d}' % n)
        (buffer,) = server._buffers.values()
        assert buffer.size == sum(len(text) for _, text in buffer.frames)
        assert server._buffers_size == buffer.size
        server._next_purge = 0
        server.broadcast_local("b", '{"n": 0}')  # "a" is stale: dropped, and its bytes
        assert list(server._buffers) == ["b"]
        assert server._buffers_size == server._buffers["b"].size

    def test_a_stream_nobody_streams_from_is_forgotten(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        conn_id = server.connect()
        server.subscribe_connection(conn_id, ["a", "b"])
        server.unsubscribe_connection(conn_id, ["a"])
        assert set(server._topics) == {"b"}
        server.client_close(conn_id)
        assert server._topics == {}

    def test_a_client_closes_once(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        first = server.connect()
        server.client_close(first)
        server.client_close(first)  # once is enough
        assert not server.is_open(first)
