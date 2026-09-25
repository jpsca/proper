import asyncio
import logging
import random

import pytest

from proper import current
from proper.channels import Channel
from proper.helpers import jsonplus
from proper.test_client import WsMessage, WsProtocolStub, make_test_ws_scope


def ws_scope(path="/cable"):
    return make_test_ws_scope(path)


async def run_ws(app, q, scope=None):
    """Run the WebSocket handler as a background task."""
    scope = scope or ws_scope()
    task = asyncio.create_task(app._handle_websocket(scope, q))
    # Let the accept happen
    await asyncio.sleep(0.01)
    return task


# --- Connection ---


class TestConnection:
    @pytest.mark.asyncio
    async def test_accepts_on_cable_path(self, app):
        q = WsProtocolStub()
        q.client_disconnect()
        task = await run_ws(app, q)
        msg = await q.client_recv()
        assert msg == {"type": "accept"}
        await task

    @pytest.mark.asyncio
    async def test_rejects_wrong_path(self, app):
        q = WsProtocolStub()
        scope = ws_scope("/wrong")
        task = await run_ws(app, q, scope)
        msg = await q.client_recv()
        assert msg == {"type": "close", "code": 404}
        await task

    @pytest.mark.asyncio
    async def test_custom_cable_path(self, app):
        app.config.CABLE_PATH = "/ws"
        q = WsProtocolStub()
        q.client_disconnect()
        task = await run_ws(app, q, ws_scope("/ws"))
        msg = await q.client_recv()
        assert msg == {"type": "accept"}
        await task


# --- Subscribe ---


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_confirms(self, app):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel

        q = WsProtocolStub()
        q.client_send({
            "command": "subscribe",
            "channel": "ChatChannel",
            "params": {"room": "general"},
        })
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "accept"

        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"
        assert confirm["channel"] == "ChatChannel"
        assert confirm["params"] == {"room": "general"}
        await task

    @pytest.mark.asyncio
    async def test_subscribe_unknown_channel(self, app):
        q = WsProtocolStub()
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

        q = WsProtocolStub()
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

        q = WsProtocolStub()
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
        q = WsProtocolStub()
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

        q = WsProtocolStub()
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

        q = WsProtocolStub()
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

        q = WsProtocolStub()
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

        q = WsProtocolStub()
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
        q = WsProtocolStub()
        q.client_send_text("not valid json{{{")
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept

        error = jsonplus.loads((await q.client_recv())["text"])
        assert error["type"] == "error"
        assert error["reason"] == "invalid_json"
        await task

    @pytest.mark.asyncio
    async def test_unknown_command(self, app):
        q = WsProtocolStub()
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
        q = WsProtocolStub()
        q.client_send_text("")
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "accept"
        # No error message - empty text is silently ignored
        await task

    @pytest.mark.asyncio
    async def test_non_receive_event_ignored(self, app):
        q = WsProtocolStub()
        # Send an unexpected event type
        q.to_app.put_nowait(WsMessage(1, b"binary frames are ignored"))
        q.client_disconnect()

        task = await run_ws(app, q)
        accept = await q.client_recv()
        assert accept["type"] == "accept"
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

        q = WsProtocolStub()
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

        q = WsProtocolStub()
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


# --- Connection scope / signed cookies ---


class TestConnectionScope:
    @pytest.mark.asyncio
    async def test_channel_reads_signed_cookie_from_scope(self, app):
        captured = {}

        class CookieChannel(Channel):
            def subscribed(self):
                captured["token"] = self.request.get_signed_cookie(
                    "_auth", salt="auth cookie"
                )

        app.router.channels["CookieChannel"] = CookieChannel

        signed = app.dumps("session-token-123", salt="auth cookie")
        scope = ws_scope()
        scope.headers = {"cookie": f"_auth={signed}"}

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "CookieChannel"})
        q.client_disconnect()

        task = await run_ws(app, q, scope)
        await q.client_recv()  # accept
        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"
        await task

        assert captured["token"] == "session-token-123"

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_none(self, app):
        captured = {}

        class NoCookieChannel(Channel):
            def subscribed(self):
                captured["token"] = self.request.get_signed_cookie(
                    "_auth", salt="auth cookie"
                )

        app.router.channels["NoCookieChannel"] = NoCookieChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "NoCookieChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)  # default scope: no cookie header
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert captured["token"] is None


# --- Session-based authentication ---


class FakeUser:
    def __init__(self, id):
        self.id = id


class FakeSession:
    def __init__(self, user):
        self.user = user
        self.user_id = user.id
        self.touched = 0

    def touch(self):
        self.touched += 1


class FakeSessionModel:
    """A stand-in for the app's Session model (`Channel.Session`)."""

    instance = FakeSession(FakeUser(7))
    find_by_token_calls = 0

    @classmethod
    def find_by_token(cls, token):
        cls.find_by_token_calls += 1
        return cls.instance if token == "good-token" else None


class FakeAuthChannel(Channel):
    """Mirrors the blueprint's `AppChannel`: wires the session model and
    implements the per-message user lookup."""

    Session = FakeSessionModel
    users = {7: FakeUser(7)}
    find_user_calls = 0

    def find_user(self, user_id):
        FakeAuthChannel.find_user_calls += 1
        return FakeAuthChannel.users.get(user_id)


def _reset_fakes():
    FakeSessionModel.instance = FakeSession(FakeUser(7))
    FakeSessionModel.find_by_token_calls = 0
    FakeAuthChannel.users = {7: FakeUser(7)}
    FakeAuthChannel.find_user_calls = 0


def _cookie_scope(app, token):
    signed = app.dumps(token, salt="auth cookie")
    scope = ws_scope()
    scope.headers = {"cookie": f"_auth={signed}"}
    return scope


class TestSessionAuth:
    @pytest.mark.asyncio
    async def test_resumes_session_and_sets_current_user(self, app):
        _reset_fakes()
        seen = {}

        class AccountChannel(FakeAuthChannel):
            def subscribed(self):
                seen["authenticated"] = self.authenticated
                seen["user_id"] = current.user.id if current.user else None

        app.router.channels["AccountChannel"] = AccountChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "AccountChannel"})
        q.client_disconnect()

        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert seen["authenticated"] is True
        assert seen["user_id"] == 7
        assert FakeSessionModel.instance.touched == 1

    @pytest.mark.asyncio
    async def test_current_user_available_in_actions(self, app):
        _reset_fakes()
        seen = {}

        class AccountChannel2(FakeAuthChannel):
            def subscribed(self):
                pass

            def whoami(self, data):
                seen["user_id"] = current.user.id if current.user else None

        app.router.channels["AccountChannel2"] = AccountChannel2

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "AccountChannel2"})
        q.client_send({
            "command": "message",
            "channel": "AccountChannel2",
            "action": "whoami",
        })
        q.client_disconnect()

        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert seen["user_id"] == 7

    @pytest.mark.asyncio
    async def test_anonymous_without_cookie(self, app):
        _reset_fakes()
        seen = {}

        class GuardedChannel(FakeAuthChannel):
            def subscribed(self):
                seen["authenticated"] = self.authenticated
                if not self.authenticated:
                    self.reject()

        app.router.channels["GuardedChannel"] = GuardedChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "GuardedChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)  # no cookie -> anonymous
        await q.client_recv()  # accept
        rejection = jsonplus.loads((await q.client_recv())["text"])
        assert rejection["type"] == "reject_subscription"
        await task

        assert seen["authenticated"] is False

    @pytest.mark.asyncio
    async def test_session_read_once_user_reloaded_per_message(self, app):
        _reset_fakes()
        seen = {"user_ids": []}

        class TickChannel(FakeAuthChannel):
            def subscribed(self):
                pass

            def ping(self, data):
                seen["user_ids"].append(current.user.id if current.user else None)

        app.router.channels["TickChannel"] = TickChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "TickChannel"})
        q.client_send({
            "command": "message",
            "channel": "TickChannel",
            "action": "ping",
        })
        q.client_send({
            "command": "message",
            "channel": "TickChannel",
            "action": "ping",
        })
        q.client_disconnect()

        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert seen["user_ids"] == [7, 7]
        # The cookie and the session were read only at subscription time
        assert FakeSessionModel.find_by_token_calls == 1
        assert FakeSessionModel.instance.touched == 1
        # The user was reloaded once per message, plus once for the
        # `unsubscribed` dispatch at disconnect
        assert FakeAuthChannel.find_user_calls == 3

    @pytest.mark.asyncio
    async def test_deleted_user_unsets_current_user(self, app):
        _reset_fakes()
        seen = {}

        class FragileChannel(FakeAuthChannel):
            def subscribed(self):
                pass

            def vanish(self, data):
                FakeAuthChannel.users.clear()

            def whoami(self, data):
                seen["user"] = current.user
                seen["authenticated"] = self.authenticated

        app.router.channels["FragileChannel"] = FragileChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "FragileChannel"})
        q.client_send({
            "command": "message",
            "channel": "FragileChannel",
            "action": "vanish",
        })
        q.client_send({
            "command": "message",
            "channel": "FragileChannel",
            "action": "whoami",
        })
        q.client_disconnect()

        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert seen["user"] is None
        # `user_id` was resolved at subscription, so the connection still
        # counts as authenticated even though the user row is gone
        assert seen["authenticated"] is True

    @pytest.mark.asyncio
    async def test_auth_session_only_in_subscribed(self, app):
        _reset_fakes()
        seen = {}

        class ProbeChannel(FakeAuthChannel):
            def subscribed(self):
                seen["in_subscribed"] = current.auth_session

            def probe(self, data):
                seen["in_action"] = current.auth_session

        app.router.channels["ProbeChannel"] = ProbeChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "ProbeChannel"})
        q.client_send({
            "command": "message",
            "channel": "ProbeChannel",
            "action": "probe",
        })
        q.client_disconnect()

        task = await run_ws(app, q, _cookie_scope(app, "good-token"))
        await q.client_recv()  # accept
        await q.client_recv()  # confirm
        await task

        assert seen["in_subscribed"] is FakeSessionModel.instance
        assert seen["in_action"] is None


# --- Outbound delivery ---


class SlowWsProtocolStub(WsProtocolStub):
    """Like `WsProtocolStub`, but sending a frame suspends before delivering.

    A real server does the same whenever the transport applies
    backpressure, which is what pulls concurrent senders out of order.
    """

    def __init__(self):
        super().__init__()
        self._rng = random.Random(1234)

    async def send_str(self, text):
        await asyncio.sleep(self._rng.uniform(0, 0.002))
        await super().send_str(text)


class BrokenWsProtocolStub(WsProtocolStub):
    """A connection that drops as soon as the app tries to write to it."""

    async def send_str(self, text):
        raise ConnectionResetError("client went away")


class TestOutboundDelivery:
    @pytest.mark.asyncio
    async def test_broadcasts_arrive_in_the_order_they_were_sent(self, app):
        class RoomChannel(Channel):
            def subscribed(self):
                self.stream_from("room")

        app.router.channels["RoomChannel"] = RoomChannel

        q = SlowWsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "RoomChannel"})

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"

        total = 25
        # Broadcast from a worker thread, the way a controller does.
        await asyncio.to_thread(
            lambda: [app.cable.broadcast("room", {"n": n}) for n in range(total)]
        )

        received = [
            jsonplus.loads((await q.client_recv())["text"])["data"]["n"]
            for _ in range(total)
        ]
        assert received == list(range(total))

        q.client_disconnect()
        await task

    @pytest.mark.asyncio
    async def test_queued_messages_are_flushed_before_closing(self, app):
        class RoomChannel(Channel):
            def subscribed(self):
                self.stream_from("room")

        app.router.channels["RoomChannel"] = RoomChannel

        q = SlowWsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "RoomChannel"})
        # The disconnect is already waiting when the confirm is queued.
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        confirm = jsonplus.loads((await q.client_recv())["text"])
        assert confirm["type"] == "confirm_subscription"
        await task

    @pytest.mark.asyncio
    async def test_a_failed_send_is_reported(self, app, caplog):
        class RoomChannel(Channel):
            def subscribed(self):
                self.stream_from("room")

        app.router.channels["RoomChannel"] = RoomChannel

        q = BrokenWsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "RoomChannel"})
        q.client_disconnect()

        with caplog.at_level(logging.ERROR, logger="proper"):
            task = await run_ws(app, q)
            await q.client_recv()  # accept
            await task

        assert "could not send to the client" in caplog.text


class TestRejectedSubscription:
    @pytest.mark.asyncio
    async def test_a_rejected_channel_does_not_leak_its_streams(self, app):
        class GuardedChannel(Channel):
            def subscribed(self):
                self.stream_from("guarded")  # set up first...
                self.reject()  # ...then decide against it

        app.router.channels["GuardedChannel"] = GuardedChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "GuardedChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        rejection = jsonplus.loads((await q.client_recv())["text"])
        assert rejection["type"] == "reject_subscription"
        await task

        assert app.cable.streams == {}

    @pytest.mark.asyncio
    async def test_a_rejected_channel_sends_nothing_to_the_client(self, app):
        class GuardedChannel(Channel):
            def subscribed(self):
                self.send({"secret": "should never arrive"})
                self.reject()

        app.router.channels["GuardedChannel"] = GuardedChannel

        q = WsProtocolStub()
        q.client_send({"command": "subscribe", "channel": "GuardedChannel"})
        q.client_disconnect()

        task = await run_ws(app, q)
        await q.client_recv()  # accept
        rejection = jsonplus.loads((await q.client_recv())["text"])
        assert rejection["type"] == "reject_subscription"
        await task

        assert q.from_app.empty()
