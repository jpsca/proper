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

    def test_everyone_gets_a_broadcast_to_all(self):
        cable = self._cable()
        server = cable.serve_in_memory()
        first, second = server.connect(), server.connect()
        server.broadcast_all("ping")
        assert server.frames(first).get_nowait() == "ping"
        assert server.frames(second).get_nowait() == "ping"
        assert server.topic_backlog("nowhere") == (0, 0, 0)
        server.client_close(first)
        server.client_close(first)  # once is enough
        assert not server.is_open(first)
