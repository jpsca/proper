"""Defects found porting Campfire to Proper. Each test fails on 0.34."""
import asyncio
import gc
import weakref

import pytest

from proper.channels import Channel
from proper.helpers import jsonplus
from proper.test_client import WsProtocolStub
from .test_websocket import (
    FakeAuthChannel,
    FakeSessionModel,
    _cookie_scope,
    _reset_fakes,
    run_ws,
)


async def _recv_json(q):
    return jsonplus.loads((await q.client_recv())["text"])


class TestDuplicateSubscription:
    @pytest.mark.asyncio
    async def test_subscribing_twice_leaves_no_stream_behind(self, app):
        """Two subscriptions with the same channel and params (two elements
        on a page, or a Turbo navigation that connects the new element before
        disconnecting the old one) used to replace the first channel without
        closing its streams. Nothing ever closed them: the disconnect only
        cleans up the channels it still knows about."""

        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel
        sub = {"command": "subscribe", "channel": "ChatChannel", "params": {"room": 1}}

        q = WsProtocolStub()
        q.client_send(sub)
        q.client_send(sub)
        q.client_disconnect()
        task = await run_ws(app, q)
        await task

        assert app.cable.streams == {}

    @pytest.mark.asyncio
    async def test_the_second_subscription_is_confirmed_once_more(self, app):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel
        sub = {"command": "subscribe", "channel": "ChatChannel", "params": {"room": 1}}

        q = WsProtocolStub()
        q.client_send(sub)
        q.client_send(sub)
        task = await run_ws(app, q)
        assert (await q.client_recv())["type"] == "accept"
        assert (await _recv_json(q))["type"] == "confirm_subscription"
        assert (await _recv_json(q))["type"] == "confirm_subscription"

        app.cable.broadcast("chat", {"n": 1})
        # Delivered once, not once per subscription.
        assert (await _recv_json(q))["data"] == {"n": 1}
        await asyncio.sleep(0.02)
        assert q.from_app.empty()

        q.client_disconnect()
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

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "AChannel"})
        q.client_send({"command": "subscribe", "channel": "BChannel"})
        q.client_send({"command": "subscribe", "channel": "AChannel", "params": {"x": 1}})
        q.client_disconnect()
        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await task

        assert FakeSessionModel.find_by_token_calls == 1
        assert FakeSessionModel.instance.touched == 1


class TestServerPing:
    @pytest.mark.asyncio
    async def test_the_server_pings_every_connection(self, app):
        """Without pings a client cannot tell a dead connection (a laptop
        that slept, a proxy that dropped it) from a quiet one, and the server
        keeps the channels of a vanished client until TCP gives up."""
        app.config.CABLE_PING_INTERVAL = 0.05

        q = WsProtocolStub()
        task = await run_ws(app, q)
        assert (await q.client_recv())["type"] == "accept"
        msg = await asyncio.wait_for(_recv_json(q), timeout=1)
        assert msg["type"] == "ping"

        q.client_disconnect()
        await task


class SlowTransport(WsProtocolStub):
    """A client that stopped reading: every send blocks."""

    def __init__(self):
        super().__init__()
        self.closed_with = None
        self.blocked = asyncio.Event()

    async def send_str(self, text):
        await self.blocked.wait()

    def close(self, code):
        self.closed_with = code
        super().close(code)


class TestSlowConsumer:
    @pytest.mark.asyncio
    async def test_a_client_that_does_not_read_is_disconnected(self, app):
        """Each connection's outbox had no limit: a client that stops reading
        made the cable process hold every message broadcast to it."""
        app.config.CABLE_MAX_PENDING = 10
        app.config.CABLE_STALL_TIMEOUT = 0.01

        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel

        q = SlowTransport()
        q.client_send({"command": "subscribe", "channel": "ChatChannel"})
        task = await run_ws(app, q)
        await asyncio.sleep(0.05)

        for n in range(20):
            app.cable.broadcast("chat", {"n": n})
        # Nothing gets through for longer than CABLE_STALL_TIMEOUT...
        await asyncio.sleep(0.05)
        # ...and the queue is past CABLE_MAX_PENDING.
        app.cable.broadcast("chat", {"n": 20})
        await asyncio.wait_for(task, timeout=1)

        assert q.closed_with is not None
        assert app.cable.streams == {}


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

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "RoomChannel"})
        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm

        app.cable.disconnect(user_id=7)
        await asyncio.wait_for(task, timeout=1)

        assert app.cable.streams == {}


class TestFanOut:
    @pytest.mark.asyncio
    async def test_every_subscriber_gets_the_same_frame(self, app):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel
        clients = []
        for _ in range(3):
            q = WsProtocolStub()
            q.client_send({"command": "subscribe", "channel": "ChatChannel", "params": {"r": 1}})
            clients.append((q, await run_ws(app, q)))
        for q, _ in clients:
            await q.client_recv()  # accept
            await q.client_recv()  # confirm

        app.cable.broadcast("chat", {"html": "<p>hi</p>"})
        frames = [(await q.client_recv())["text"] for q, _ in clients]
        assert len(set(frames)) == 1
        assert jsonplus.loads(frames[0]) == {
            "type": "message", "channel": "ChatChannel", "params": {"r": 1},
            "data": {"html": "<p>hi</p>"},
        }
        for q, task in clients:
            q.client_disconnect()
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


class BusyTransport(WsProtocolStub):
    """A client that reads, behind a server that is falling behind."""

    def __init__(self):
        super().__init__()
        self.closed_with = None

    async def send_str(self, text):
        await asyncio.sleep(0)

    def close(self, code):
        self.closed_with = code
        super().close(code)


class TestBusyServer:
    @pytest.mark.asyncio
    async def test_a_client_that_reads_is_kept_when_the_server_falls_behind(self, app):
        app.config.CABLE_MAX_PENDING = 10

        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel

        q = BusyTransport()
        q.client_send({"command": "subscribe", "channel": "ChatChannel"})
        task = await run_ws(app, q)
        await asyncio.sleep(0.05)

        for n in range(50):  # more than the limit, at once
            app.cable.broadcast("chat", {"n": n})
        await asyncio.sleep(0.05)

        assert q.closed_with is None
        assert app.cable.streams == {"chat": 1}
        q.client_disconnect()
        await task
