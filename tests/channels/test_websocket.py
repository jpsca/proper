import asyncio

import pytest

from proper.channel import Channel
from proper.helpers import jsonplus


class AsyncQueue:
    """Simulates ASGI receive/send as async queues."""

    def __init__(self):
        self.to_app = asyncio.Queue()
        self.from_app = asyncio.Queue()

    async def receive(self):
        return await self.to_app.get()

    async def send(self, msg):
        await self.from_app.put(msg)

    def client_send(self, data):
        """Queue a JSON message from the client."""
        self.to_app.put_nowait({
            "type": "websocket.receive",
            "text": jsonplus.dumps(data),
        })

    def client_disconnect(self):
        self.to_app.put_nowait({"type": "websocket.disconnect"})

    async def client_recv(self, timeout=1.0):
        """Get the next message sent by the app to the client."""
        return await asyncio.wait_for(self.from_app.get(), timeout=timeout)


def ws_scope(path="/cable"):
    return {
        "type": "websocket",
        "path": path,
        "headers": [],
        "query_string": b"",
    }


async def run_ws(app, q, scope=None):
    """Run handle_websocket as a background task."""
    scope = scope or ws_scope()
    task = asyncio.create_task(app._handle_websocket(scope, q.receive, q.send))
    # Let the accept happen
    await asyncio.sleep(0.01)
    return task


# --- Connection ---


class TestConnection:
    @pytest.mark.asyncio
    async def test_accepts_on_cable_path(self, app):
        q = AsyncQueue()
        q.client_disconnect()
        task = await run_ws(app, q)
        msg = await q.client_recv()
        assert msg == {"type": "websocket.accept"}
        await task

    @pytest.mark.asyncio
    async def test_rejects_wrong_path(self, app):
        q = AsyncQueue()
        scope = ws_scope("/wrong")
        task = await run_ws(app, q, scope)
        msg = await q.client_recv()
        assert msg == {"type": "websocket.close", "code": 4004}
        await task

    @pytest.mark.asyncio
    async def test_custom_cable_path(self, app):
        app.config.CABLE_PATH = "/ws"
        q = AsyncQueue()
        q.client_disconnect()
        task = await run_ws(app, q, ws_scope("/ws"))
        msg = await q.client_recv()
        assert msg == {"type": "websocket.accept"}
        await task


# --- Subscribe ---


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_confirms(self, app):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel

        q = AsyncQueue()
        q.client_send({
            "command": "subscribe",
            "channel": "ChatChannel",
            "params": {"room": "general"},
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "websocket.accept"

        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"
        assert confirm["channel"] == "ChatChannel"
        assert confirm["params"] == {"room": "general"}
        await task

    @pytest.mark.asyncio
    async def test_subscribe_unknown_channel(self, app):
        q = AsyncQueue()
        q.client_send({
            "command": "subscribe",
            "channel": "NonexistentChannel",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        rejection = jsonplus.loads((await q.client_recv())["text"])
        assert rejection["type"] == "reject_subscription"
        assert rejection["reason"] == "unknown_channel"
        await task

    @pytest.mark.asyncio
    async def test_subscribe_rejected_by_channel(self, app):
        class PrivateChannel(Channel):
            def subscribed(self):
                self.reject()

        app.router.channels["PrivateChannel"] = PrivateChannel

        q = AsyncQueue()
        q.client_send({
            "command": "subscribe",
            "channel": "PrivateChannel",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        rejection = jsonplus.loads((await q.client_recv())["text"])
        assert rejection["type"] == "reject_subscription"
        assert rejection["channel"] == "PrivateChannel"
        await task


# --- Message ---


class TestMessage:
    @pytest.mark.asyncio
    async def test_dispatch_action(self, app):
        received = []

        class EchoChannel(Channel):
            def subscribed(self):
                pass

            def speak(self, data):
                received.append(data)
                self.send({"echo": data["text"]})

        app.router.channels["EchoChannel"] = EchoChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "EchoChannel"})
        q.client_send({
            "command": "message",
            "channel": "EchoChannel",
            "action": "speak",
            "data": {"text": "hello"},
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"

        # The echo response
        echo = jsonplus.loads((await q.client_recv())["text"])
        assert echo["type"] == "message"
        assert echo["data"] == {"echo": "hello"}
        assert received == [{"text": "hello"}]
        await task

    @pytest.mark.asyncio
    async def test_message_not_subscribed(self, app):
        q = AsyncQueue()
        q.client_send({
            "command": "message",
            "channel": "SomeChannel",
            "action": "speak",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        error = jsonplus.loads((await q.client_recv())["text"])
        assert error["type"] == "error"
        assert error["reason"] == "not_subscribed"
        await task

    @pytest.mark.asyncio
    async def test_invalid_action_rejected(self, app):
        class TestChannel(Channel):
            def subscribed(self):
                pass

        app.router.channels["TestChannel"] = TestChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "TestChannel"})
        # Try calling a private method
        q.client_send({
            "command": "message",
            "channel": "TestChannel",
            "action": "_dispatch",
        })
        # Try calling subscribed directly
        q.client_send({
            "command": "message",
            "channel": "TestChannel",
            "action": "subscribed",
        })
        # Try calling unsubscribed directly
        q.client_send({
            "command": "message",
            "channel": "TestChannel",
            "action": "unsubscribed",
        })
        # Try empty action
        q.client_send({
            "command": "message",
            "channel": "TestChannel",
            "action": "",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        await q.client_recv()  # confirm

        for _ in range(4):
            error = jsonplus.loads((await q.client_recv())["text"])
            assert error["type"] == "error"
            assert error["reason"] == "invalid_action"
        await task

    @pytest.mark.asyncio
    async def test_unknown_action_rejected(self, app):
        class TestChannel(Channel):
            def subscribed(self):
                pass

        app.router.channels["TestChannel"] = TestChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "TestChannel"})
        q.client_send({
            "command": "message",
            "channel": "TestChannel",
            "action": "nonexistent",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        await q.client_recv()  # confirm

        error = jsonplus.loads((await q.client_recv())["text"])
        assert error["type"] == "error"
        assert error["reason"] == "unknown_action"
        await task


# --- Unsubscribe ---


class TestUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_calls_lifecycle(self, app):
        lifecycle = []

        class TrackChannel(Channel):
            def subscribed(self):
                lifecycle.append("subscribed")

            def unsubscribed(self):
                lifecycle.append("unsubscribed")

        app.router.channels["TrackChannel"] = TrackChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "TrackChannel"})
        q.client_send({"command": "unsubscribe", "channel": "TrackChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert lifecycle == ["subscribed", "unsubscribed"]

    @pytest.mark.asyncio
    async def test_disconnect_calls_unsubscribed(self, app):
        lifecycle = []

        class TrackChannel(Channel):
            def subscribed(self):
                lifecycle.append("subscribed")

            def unsubscribed(self):
                lifecycle.append("unsubscribed")

        app.router.channels["TrackChannel"] = TrackChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "TrackChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert lifecycle == ["subscribed", "unsubscribed"]


# --- Error handling ---


class TestProtocolErrors:
    @pytest.mark.asyncio
    async def test_invalid_json(self, app):
        q = AsyncQueue()
        q.to_app.put_nowait({
            "type": "websocket.receive",
            "text": "not valid json{{{",
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        error = jsonplus.loads((await q.client_recv())["text"])
        assert error["type"] == "error"
        assert error["reason"] == "invalid_json"
        await task

    @pytest.mark.asyncio
    async def test_unknown_command(self, app):
        q = AsyncQueue()
        q.client_send({"command": "bogus"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        error = jsonplus.loads((await q.client_recv())["text"])
        assert error["type"] == "error"
        assert error["reason"] == "unknown_command"
        await task

    @pytest.mark.asyncio
    async def test_empty_text_ignored(self, app):
        q = AsyncQueue()
        q.to_app.put_nowait({"type": "websocket.receive", "text": ""})
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "websocket.accept"
        # No error message - empty text is silently ignored
        await task

    @pytest.mark.asyncio
    async def test_non_receive_event_ignored(self, app):
        q = AsyncQueue()
        # Send an unexpected event type
        q.to_app.put_nowait({"type": "websocket.ping"})
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "websocket.accept"
        await task


# --- Messages sent during subscribed() ---


class TestDisconnectErrorHandling:
    @pytest.mark.asyncio
    async def test_error_in_unsubscribed_is_logged(self, app):
        class BadChannel(Channel):
            def subscribed(self):
                pass

            def unsubscribed(self):
                raise RuntimeError("cleanup failed")

        app.router.channels["BadChannel"] = BadChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "BadChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        # Should not raise - error is logged
        await task


class TestSendDuringSubscribed:
    @pytest.mark.asyncio
    async def test_messages_sent_in_subscribed_are_flushed(self, app):
        class GreetChannel(Channel):
            def subscribed(self):
                self.send({"greeting": "welcome!"})

        app.router.channels["GreetChannel"] = GreetChannel

        q = AsyncQueue()
        q.client_send({"command": "subscribe", "channel": "GreetChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        # The greeting is flushed before the confirm
        greeting = jsonplus.loads((await q.client_recv())["text"])
        assert greeting["type"] == "message"
        assert greeting["data"] == {"greeting": "welcome!"}

        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"
        await task
