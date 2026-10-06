"""The WebSocket protocol of the channels, as the cable (`WseCable`) serves
it, driven from memory through `TestClient.websocket()`."""
import logging

import pytest

from proper import App, current
from proper.channels import Channel
from proper.test_client import TestClient


SECRET = "*" * 50


def make_wse_app() -> App:
    """An app whose cable is `WseCable`."""
    app = App("proper", {
        "SECRET_KEYS": [SECRET],
        "DEBUG": False,
        "CABLE": {"type": "proper.channels.wse.WseCable"},
    })
    current.app = app
    return app


@pytest.fixture()
def app():
    app = make_wse_app()
    yield app
    app.cable.stop_server()


async def open_ws(app, cookie: str = ""):
    """Connect a client, with `cookie` in its handshake. Returns the session
    and the task that ends with the connection."""
    client = TestClient(app)
    if cookie:
        client.default_headers["cookie"] = cookie
    ws = client.websocket()
    task = await ws.connect()
    return ws, task


async def nothing_more(ws):
    with pytest.raises(TimeoutError):
        await ws.receive(timeout=0.05)


# --- Subscribe ---


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_confirms(self, app):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from("chat")

        app.router.channels["ChatChannel"] = ChatChannel

        ws, task = await open_ws(app)
        confirm = await ws.subscribe("ChatChannel", room="general")
        assert confirm["type"] == "confirm_subscription"
        assert confirm["channel"] == "ChatChannel"
        assert confirm["params"] == {"room": "general"}
        assert confirm["streams"] == ["chat"]
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_subscribe_unknown_channel(self, app):
        ws, task = await open_ws(app)
        rejection = await ws.subscribe("NonexistentChannel")
        assert rejection["type"] == "reject_subscription"
        assert rejection["reason"] == "unknown_channel"
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_subscribe_rejected_by_channel(self, app):
        class PrivateChannel(Channel):
            def subscribed(self):
                self.reject()

        app.router.channels["PrivateChannel"] = PrivateChannel

        ws, task = await open_ws(app)
        rejection = await ws.subscribe("PrivateChannel")
        assert rejection["type"] == "reject_subscription"
        assert rejection["channel"] == "PrivateChannel"
        await ws.close()
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

        ws, task = await open_ws(app)
        confirm = await ws.subscribe("EchoChannel")
        assert confirm["type"] == "confirm_subscription"
        await ws.send_action("EchoChannel", "speak", {"text": "hello"})

        echo = await ws.receive()
        assert echo["type"] == "message"
        assert echo["channel"] == "EchoChannel"
        assert echo["data"] == {"echo": "hello"}
        assert received == [{"text": "hello"}]
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_message_not_subscribed(self, app):
        ws, task = await open_ws(app)
        await ws.send_action("SomeChannel", "speak")

        error = await ws.receive()
        assert error["type"] == "error"
        assert error["reason"] == "not_subscribed"
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_invalid_action_rejected(self, app):
        class TestChannel(Channel):
            def subscribed(self):
                pass

        app.router.channels["TestChannel"] = TestChannel

        ws, task = await open_ws(app)
        await ws.subscribe("TestChannel")
        # A private method, the lifecycle methods, and no action at all
        for action in ("_dispatch", "subscribed", "unsubscribed", ""):
            await ws.send_action("TestChannel", action)
            error = await ws.receive()
            assert error["type"] == "error"
            assert error["reason"] == "invalid_action"
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_unknown_action_rejected(self, app):
        class TestChannel(Channel):
            def subscribed(self):
                pass

        app.router.channels["TestChannel"] = TestChannel

        ws, task = await open_ws(app)
        await ws.subscribe("TestChannel")
        await ws.send_action("TestChannel", "nonexistent")

        error = await ws.receive()
        assert error["type"] == "error"
        assert error["reason"] == "unknown_action"
        await ws.close()
        await task


# --- Unsubscribe ---


class TrackChannel(Channel):
    lifecycle: list = []

    def subscribed(self):
        self.lifecycle.append("subscribed")

    def unsubscribed(self):
        self.lifecycle.append("unsubscribed")


class TestUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_calls_lifecycle(self, app):
        TrackChannel.lifecycle = []
        app.router.channels["TrackChannel"] = TrackChannel

        ws, task = await open_ws(app)
        await ws.subscribe("TrackChannel")
        await ws.unsubscribe("TrackChannel")
        assert TrackChannel.lifecycle == ["subscribed", "unsubscribed"]

        await ws.close()
        await task
        # Not again at the disconnect: the subscription was already gone.
        assert TrackChannel.lifecycle == ["subscribed", "unsubscribed"]

    @pytest.mark.asyncio
    async def test_disconnect_calls_unsubscribed(self, app):
        TrackChannel.lifecycle = []
        app.router.channels["TrackChannel"] = TrackChannel

        ws, task = await open_ws(app)
        await ws.subscribe("TrackChannel")
        await ws.close()
        await task

        assert TrackChannel.lifecycle == ["subscribed", "unsubscribed"]


# --- Error handling ---


class TestProtocolErrors:
    @pytest.mark.asyncio
    async def test_invalid_json(self, app):
        ws, task = await open_ws(app)
        ws.client_send_text("not valid json{{{")

        error = await ws.receive()
        assert error["type"] == "error"
        assert error["reason"] == "invalid_json"
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_unknown_command(self, app):
        ws, task = await open_ws(app)
        ws.client_send({"command": "bogus"})

        error = await ws.receive()
        assert error["type"] == "error"
        assert error["reason"] == "unknown_command"
        await ws.close()
        await task


class TestDisconnectErrorHandling:
    @pytest.mark.asyncio
    async def test_error_in_unsubscribed_is_logged(self, app, caplog):
        class BadChannel(Channel):
            def subscribed(self):
                pass

            def unsubscribed(self):
                raise RuntimeError("cleanup failed")

        app.router.channels["BadChannel"] = BadChannel

        ws, task = await open_ws(app)
        await ws.subscribe("BadChannel")
        with caplog.at_level(logging.ERROR, logger="proper"):
            # Should not raise - the error is logged
            await ws.close()
            await task

        assert "cleanup failed" in caplog.text


# --- Messages sent during subscribed() ---


class TestSendDuringSubscribed:
    @pytest.mark.asyncio
    async def test_messages_sent_in_subscribed_are_flushed(self, app):
        class GreetChannel(Channel):
            def subscribed(self):
                self.send({"greeting": "welcome!"})

        app.router.channels["GreetChannel"] = GreetChannel

        ws, task = await open_ws(app)
        # The greeting is flushed before the confirm
        greeting = await ws.subscribe("GreetChannel")
        assert greeting["type"] == "message"
        assert greeting["data"] == {"greeting": "welcome!"}

        confirm = await ws.receive()
        assert confirm["type"] == "confirm_subscription"
        await ws.close()
        await task


# --- The handshake's signed cookies ---


class CookieChannel(Channel):
    captured: dict = {}

    def subscribed(self):
        self.captured["token"] = self.request.get_signed_cookie(
            "_auth", salt="auth cookie"
        )


class TestConnectionCookies:
    @pytest.mark.asyncio
    async def test_channel_reads_signed_cookie_from_the_handshake(self, app):
        CookieChannel.captured = {}
        app.router.channels["CookieChannel"] = CookieChannel

        signed = app.dumps("session-token-123", salt="auth cookie")
        ws, task = await open_ws(app, f"_auth={signed}")
        confirm = await ws.subscribe("CookieChannel")
        assert confirm["type"] == "confirm_subscription"
        await ws.close()
        await task

        assert CookieChannel.captured["token"] == "session-token-123"

    @pytest.mark.asyncio
    async def test_missing_cookie_returns_none(self, app):
        CookieChannel.captured = {}
        app.router.channels["CookieChannel"] = CookieChannel

        ws, task = await open_ws(app)  # no cookie header
        await ws.subscribe("CookieChannel")
        await ws.close()
        await task

        assert CookieChannel.captured["token"] is None


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


def _cookie(app, token):
    """The `cookie` header of a client signed in with session `token`."""
    return "_auth=" + app.dumps(token, salt="auth cookie")


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

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("AccountChannel")
        await ws.close()
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

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("AccountChannel2")
        await ws.send_action("AccountChannel2", "whoami")
        await ws.close()
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

        ws, task = await open_ws(app)  # no cookie -> anonymous
        rejection = await ws.subscribe("GuardedChannel")
        assert rejection["type"] == "reject_subscription"
        await ws.close()
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

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("TickChannel")
        await ws.send_action("TickChannel", "ping")
        await ws.send_action("TickChannel", "ping")
        await ws.close()
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

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("FragileChannel")
        await ws.send_action("FragileChannel", "vanish")
        await ws.send_action("FragileChannel", "whoami")
        await ws.close()
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

        ws, task = await open_ws(app, _cookie(app, "good-token"))
        await ws.subscribe("ProbeChannel")
        await ws.send_action("ProbeChannel", "probe")
        await ws.close()
        await task

        assert seen["in_subscribed"] is FakeSessionModel.instance
        assert seen["in_action"] is None


class TestRejectedSubscription:
    @pytest.mark.asyncio
    async def test_a_rejected_channel_does_not_leak_its_streams(self, app):
        class GuardedChannel(Channel):
            def subscribed(self):
                self.stream_from("guarded")  # set up first...
                self.reject()  # ...then decide against it

        app.router.channels["GuardedChannel"] = GuardedChannel

        ws, task = await open_ws(app)
        rejection = await ws.subscribe("GuardedChannel")
        assert rejection["type"] == "reject_subscription"
        assert app.cable.streams == {}

        app.cable.broadcast("guarded", {"secret": "should never arrive"})
        await nothing_more(ws)
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_a_rejected_channel_sends_nothing_to_the_client(self, app):
        class GuardedChannel(Channel):
            def subscribed(self):
                self.send({"secret": "should never arrive"})
                self.reject()

        app.router.channels["GuardedChannel"] = GuardedChannel

        ws, task = await open_ws(app)
        rejection = await ws.subscribe("GuardedChannel")
        assert rejection["type"] == "reject_subscription"
        await nothing_more(ws)
        await ws.close()
        await task
