"""Defects found porting Campfire to Proper. Each test fails on 0.34."""
import gc
import weakref

import pytest

from proper.channels import Channel
from proper.helpers import jsonplus
from .test_websocket import (
    FakeAuthChannel,
    FakeSessionModel,
    _cookie,
    _reset_fakes,
    make_wse_app,
    nothing_more,
    open_ws,
)


@pytest.fixture()
def app():
    app = make_wse_app()
    yield app
    app.cable.stop_server()


class ChatChannel(Channel):
    def subscribed(self):
        self.stream_from("chat")


class TestDuplicateSubscription:
    @pytest.mark.asyncio
    async def test_subscribing_twice_leaves_no_stream_behind(self, app):
        """Two subscriptions with the same channel and params (two elements
        on a page, or a Turbo navigation that connects the new element before
        disconnecting the old one) used to replace the first channel without
        closing its streams. Nothing ever closed them: the disconnect only
        cleans up the channels it still knows about."""
        app.router.channels["ChatChannel"] = ChatChannel

        ws, task = await open_ws(app)
        await ws.subscribe("ChatChannel", room=1)
        await ws.subscribe("ChatChannel", room=1)
        await ws.close()
        await task

        assert app.cable.streams == {}

    @pytest.mark.asyncio
    async def test_the_second_subscription_is_confirmed_once_more(self, app):
        app.router.channels["ChatChannel"] = ChatChannel

        ws, task = await open_ws(app)
        assert (await ws.subscribe("ChatChannel", room=1))["type"] == "confirm_subscription"
        assert (await ws.subscribe("ChatChannel", room=1))["type"] == "confirm_subscription"

        app.cable.broadcast("chat", {"n": 1})
        # Delivered once, not once per subscription.
        assert (await ws.receive())["data"] == {"n": 1}
        await nothing_more(ws)

        await ws.close()
        await task


class TestAuthenticationPerConnection:
    @pytest.mark.asyncio
    async def test_the_session_is_read_once_per_connection(self, app):
        """Campfire's room page opens six subscriptions on one socket. Each
        one used to verify the cookie, look up the session and touch it."""
        _reset_fakes()

        class AChannel(FakeAuthChannel):
            pass

        class BChannel(FakeAuthChannel):
            pass

        app.router.channels["AChannel"] = AChannel
        app.router.channels["BChannel"] = BChannel

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("AChannel")
        await ws.subscribe("BChannel")
        await ws.subscribe("AChannel", x=1)
        await ws.close()
        await task

        assert FakeSessionModel.find_by_token_calls == 1
        assert FakeSessionModel.instance.touched == 1


class TestRemoteDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_the_connections_of_a_user(self, app):
        """Revoking a membership, banning or deactivating a user, signing
        out: Campfire closes that user's open connections, so channels
        authorized at subscription time stop delivering."""
        _reset_fakes()

        class RoomChannel(FakeAuthChannel):
            def subscribed(self):
                self.stream_from("room")

        app.router.channels["RoomChannel"] = RoomChannel

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("RoomChannel")

        app.cable.disconnect(user_id=7)
        assert await ws.receive() == {"type": "close", "code": 1000}
        await task

        assert app.cable.streams == {}


class TestFanOut:
    @pytest.mark.asyncio
    async def test_every_subscriber_gets_the_same_frame(self, app):
        """A broadcast is encoded once: its frame names the stream, not the
        channel and params of each subscription, so it is the same text for
        every subscriber."""
        app.router.channels["ChatChannel"] = ChatChannel
        clients = []
        for r in range(3):
            ws, task = await open_ws(app)
            await ws.subscribe("ChatChannel", r=r)
            clients.append((ws, task))

        app.cable.broadcast("chat", {"html": "<p>hi</p>"})
        frames = [(await ws.receive_raw())["text"] for ws, _ in clients]
        assert len(set(frames)) == 1
        frame = jsonplus.loads(frames[0])
        assert frame == {
            # wse's recovery stamp, then Proper's frame
            "tp": "chat", "e": frame["e"], "o": 0,
            "c": "P", "type": "broadcast", "stream": "chat",
            "data": {"html": "<p>hi</p>"},
        }
        for ws, task in clients:
            await ws.close()
            await task


class TestNoCyclicGarbage:
    def test_a_response_is_freed_without_the_cycle_collector(self, app):
        """`Response.flash` pointed back to the response: every response, and
        its body, waited for the cycle collector, which runs by count of
        objects, not by their size. Pages of 400 KB piled up into gigabytes."""
        from proper.core.response import Response

        gc.disable()
        try:
            response = Response(app)
            response.body = "x" * 1000
            ref = weakref.ref(response)
            del response
            assert ref() is None
        finally:
            gc.enable()

    def test_loads_leaves_no_cyclic_garbage(self):
        gc.collect()
        gc.disable()
        try:
            before = gc.get_count()[0]
            for _ in range(50):
                jsonplus.loads('{"a": 1}')
            assert gc.collect() == 0, before
        finally:
            gc.enable()
