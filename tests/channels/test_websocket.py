"""The WebSocket protocol of the channels, as the cable (`Cable`) serves
it, driven from memory through `TestClient.websocket()`."""
import logging

import pytest

from proper import App, current
from proper.channels import ActionError, Channel
from proper.test_client import TestClient


SECRET = "*" * 50


def make_wse_app() -> App:
    """An app whose cable is `Cable`."""
    app = App("proper", {
        "SECRET_KEYS": [SECRET],
        "DEBUG": False,
        "CABLE": {"type": "proper.channels.Cable"},
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
    async def test_a_channel_registered_under_another_name(self, app):
        """Its messages carry the name the client subscribed with, so the
        client can find the subscription."""
        class ChatChannel(Channel):
            def subscribed(self):
                self.send({"hello": 1})

        app.router.channel("chat")(ChatChannel)

        ws, task = await open_ws(app)
        hello = await ws.subscribe("chat")
        assert hello == {
            "type": "message", "channel": "chat", "params": {}, "data": {"hello": 1},
        }
        confirm = await ws.receive()
        assert confirm["type"] == "confirm_subscription"
        assert confirm["channel"] == "chat"
        await ws.close()
        await task

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

    @pytest.mark.asyncio
    async def test_subscribed_that_fails_is_rejected(self, app, caplog):
        """The streams it reached before failing are closed: none of their
        broadcasts get to a client whose subscription was never confirmed."""
        class BrokenChannel(Channel):
            def subscribed(self):
                self.stream_from("secret")
                self.send({"hello": 1})
                raise RuntimeError("boom")

        app.router.channels["BrokenChannel"] = BrokenChannel

        ws, task = await open_ws(app)
        with caplog.at_level(logging.ERROR):
            rejection = await ws.subscribe("BrokenChannel")
        assert rejection == {
            "type": "reject_subscription", "channel": "BrokenChannel",
            "params": {}, "reason": "error",
        }
        assert "error handling a command" in caplog.text
        assert app.cable.streams == {}

        app.cable.broadcast("secret", {"x": 1})
        await nothing_more(ws)
        await ws.close()
        await task
        assert app.cable.streams == {}


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
    async def test_reply_to_an_action_with_an_id(self, app):
        """What the action returns is the data of the reply; what it sent
        before comes first."""
        class EchoChannel(Channel):
            def subscribed(self):
                pass

            def speak(self, data):
                self.send({"echo": data["text"]})
                return {"length": len(data["text"])}

            def wave(self, data):
                pass

        app.router.channels["EchoChannel"] = EchoChannel

        ws, task = await open_ws(app)
        await ws.subscribe("EchoChannel")
        await ws.send_action("EchoChannel", "speak", {"text": "hello"}, id=7)
        assert (await ws.receive())["type"] == "message"
        assert await ws.receive() == {
            "type": "reply", "id": 7, "channel": "EchoChannel", "params": {},
            "status": "ok", "data": {"length": 5},
        }
        # Without an id, no reply
        await ws.send_action("EchoChannel", "speak", {"text": "hello"})
        assert (await ws.receive())["type"] == "message"
        await nothing_more(ws)
        # `perform()` skips what the action sends and returns the reply
        reply = await ws.perform("EchoChannel", "speak", {"text": "hi"})
        assert reply["status"] == "ok" and reply["data"] == {"length": 2}
        # An action that returns nothing replies `null`
        reply = await ws.perform("EchoChannel", "wave", {})
        assert reply["status"] == "ok" and reply["data"] is None
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_reply_with_an_action_error(self, app, caplog):
        class EchoChannel(Channel):
            def subscribed(self):
                pass

            def speak(self, data):
                raise ActionError("too_long", max=5)

        app.router.channels["EchoChannel"] = EchoChannel

        ws, task = await open_ws(app)
        await ws.subscribe("EchoChannel")
        with caplog.at_level(logging.ERROR):
            reply = await ws.perform("EchoChannel", "speak", {"text": "hello world"})
        assert reply["status"] == "error"
        assert reply["data"] == {"reason": "too_long", "max": 5}
        assert caplog.text == ""  # the action's answer, not a failure
        # Without an id, as an error frame
        await ws.send_action("EchoChannel", "speak", {"text": "hello world"})
        assert await ws.receive() == {"type": "error", "reason": "too_long", "max": 5}
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_reply_when_the_action_fails(self, app, caplog):
        """The client learns that it failed; the log, why."""
        class EchoChannel(Channel):
            def subscribed(self):
                pass

            def speak(self, data):
                raise RuntimeError("the database is gone")

        app.router.channels["EchoChannel"] = EchoChannel

        ws, task = await open_ws(app)
        await ws.subscribe("EchoChannel")
        with caplog.at_level(logging.ERROR):
            reply = await ws.perform("EchoChannel", "speak", {})
        assert reply["status"] == "error"
        assert reply["data"] == {"reason": "error"}
        assert "the database is gone" in caplog.text
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_protocol_errors_reply_to_an_id(self, app):
        class TestChannel(Channel):
            def subscribed(self):
                pass

        app.router.channels["TestChannel"] = TestChannel

        ws, task = await open_ws(app)
        reply = await ws.perform("TestChannel", "speak", room="x")
        assert reply == {
            "type": "reply", "id": 1, "channel": "TestChannel", "params": {"room": "x"},
            "status": "error", "data": {"reason": "not_subscribed"},
        }
        await ws.subscribe("TestChannel")
        reply = await ws.perform("TestChannel", "_dispatch")
        assert reply["data"] == {"reason": "invalid_action"}
        reply = await ws.perform("TestChannel", "speak")
        assert reply["data"] == {"reason": "unknown_action"}
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
        # A private method, the lifecycle methods, the user loader, and no
        # action at all
        for action in ("_dispatch", "subscribed", "unsubscribed", "find_user", ""):
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


# --- Recovery ---


class RoomChannel(Channel):
    def subscribed(self):
        self.stream_from(f"room_{self.params['room']}")


class TestRecovery:
    """The broadcasts a connection missed are sent again when it subscribes
    with where it was in the streams (see `Cable._confirm`)."""

    def position(self, frame: dict) -> dict:
        return {"e": frame["e"], "o": frame["o"]}

    @pytest.mark.asyncio
    async def test_broadcasts_are_stamped_and_positions_confirmed(self, app):
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        confirm = await ws.subscribe("RoomChannel", room="a")
        # No broadcast yet: no position, and nothing asked for
        assert confirm["positions"] == {"room_a": None}
        assert confirm["recovered"] is None

        app.cable.broadcast("room_a", {"n": 1})
        app.cable.broadcast("room_a", {"n": 2})
        first, second = await ws.receive(), await ws.receive()
        assert first["tp"] == "room_a" and first["stream"] == "room_a"
        assert first["data"] == {"n": 1} and second["data"] == {"n": 2}
        assert first["e"] == second["e"] and second["o"] == first["o"] + 1

        # Another connection subscribing now is told where the stream is
        ws2, task2 = await open_ws(app)
        confirm = await ws2.subscribe("RoomChannel", room="a")
        assert confirm["positions"] == {"room_a": self.position(second)}
        for w, tk in ((ws, task), (ws2, task2)):
            await w.close()
            await tk

    @pytest.mark.asyncio
    async def test_missed_broadcasts_are_sent_again(self, app):
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        await ws.subscribe("RoomChannel", room="a")
        app.cable.broadcast("room_a", {"n": 1})
        seen = await ws.receive()
        await ws.close()
        await task

        # Missed while away
        app.cable.broadcast("room_a", {"n": 2})
        app.cable.broadcast("room_a", {"n": 3})
        app.cable.broadcast("room_b", {"n": 9})  # another stream

        ws, task = await open_ws(app)
        positions = {"room_a": self.position(seen), "room_b": {"e": "0000abcd", "o": 0}}
        missed = await ws.subscribe("RoomChannel", positions=positions, room="a")
        assert missed["data"] == {"n": 2}
        assert (await ws.receive())["data"] == {"n": 3}
        confirm = await ws.receive()
        assert confirm["type"] == "confirm_subscription"
        assert confirm["recovered"] is True
        assert confirm["positions"]["room_a"]["o"] == seen["o"] + 2
        # Only the streams the channel streams from: nothing of room_b
        await nothing_more(ws)
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_several_epochs_per_stream(self, app):
        """A client of a cluster has a position per machine that published
        to the stream; each is recovered on its own. One the server doesn't
        know is not recovered."""
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        await ws.subscribe("RoomChannel", room="a")
        app.cable.broadcast("room_a", {"n": 1})
        seen = await ws.receive()
        app.cable.broadcast("room_a", {"n": 2})
        await ws.receive()
        positions = {"room_a": [self.position(seen)]}
        missed = await ws.subscribe("RoomChannel", positions=positions, room="a")
        assert missed["data"] == {"n": 2}
        assert (await ws.receive())["recovered"] is True
        positions = {"room_a": [self.position(seen), {"e": "0000abcd", "o": 3}]}
        missed = await ws.subscribe("RoomChannel", positions=positions, room="a")
        assert missed["data"] == {"n": 2}
        assert (await ws.receive())["recovered"] is False
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_up_to_date_recovers_nothing(self, app):
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        await ws.subscribe("RoomChannel", room="a")
        app.cable.broadcast("room_a", {"n": 1})
        seen = await ws.receive()
        confirm = await ws.subscribe("RoomChannel", positions={"room_a": self.position(seen)}, room="a")
        assert confirm["type"] == "confirm_subscription"
        assert confirm["recovered"] is True
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_not_recovered(self, app):
        """Another epoch (the server restarted), a gap longer than the
        buffer, or a stream without history: the client is told to load
        the state again, and gets the current position."""
        app.cable = type(app.cable)(recovery_buffer_size=4)
        app.cable.bind(app)
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        await ws.subscribe("RoomChannel", room="a")
        app.cable.broadcast("room_a", {"n": 0})
        seen = await ws.receive()

        other_epoch = {"e": "0000abcd" if seen["e"] != "0000abcd" else "0000abce", "o": seen["o"]}
        confirm = await ws.subscribe("RoomChannel", positions={"room_a": other_epoch}, room="a")
        assert confirm["recovered"] is False
        assert confirm["positions"] == {"room_a": self.position(seen)}

        for n in range(1, 6):  # more than the buffer holds
            app.cable.broadcast("room_a", {"n": n})
        for _ in range(5):
            await ws.receive()
        confirm = await ws.subscribe("RoomChannel", positions={"room_a": self.position(seen)}, room="a")
        assert confirm["recovered"] is False
        assert confirm["positions"]["room_a"]["o"] == seen["o"] + 5
        # The oldest the buffer holds is recoverable
        confirm = await ws.subscribe(
            "RoomChannel", positions={"room_a": {"e": seen["e"], "o": seen["o"] + 1}}, room="a"
        )
        assert confirm["type"] == "broadcast" and confirm["data"] == {"n": 2}

        ws2, task2 = await open_ws(app)
        confirm = await ws2.subscribe("RoomChannel", positions={"room_z": {"e": seen["e"], "o": 0}}, room="z")
        assert confirm["recovered"] is False
        assert confirm["positions"] == {"room_z": None}
        for w, tk in ((ws, task), (ws2, task2)):
            await w.close()
            await tk

    @pytest.mark.asyncio
    async def test_malformed_positions_are_ignored(self, app):
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        for positions in (
            "nope", {"room_a": "nope"}, {"room_a": {"e": "xyz", "o": 1}}, {"room_a": ["nope"]},
            {"room_a": {"e": "0000abcd", "o": -1}}, {"room_a": {"e": "0000abcd", "o": True}},
            {3: {"e": "0000abcd", "o": 1}},
        ):
            ws.client_send({
                "command": "subscribe", "channel": "RoomChannel",
                "params": {"room": "a"}, "positions": positions,
            })
            confirm = await ws.receive()
            assert confirm["type"] == "confirm_subscription"
            assert confirm["recovered"] is None
        await ws.close()
        await task

    def test_positions_with_keys_that_are_not_streams(self):
        from proper.channels.cable import _client_positions

        assert _client_positions({3: {"e": "0000abcd", "o": 1}, "s": [{"e": "0000abcd", "o": 1}]}) == {
            "s": [("0000abcd", 1)],
        }

    @pytest.mark.asyncio
    async def test_a_cluster_of_one_from_memory(self, app):
        """A cable configured for a cluster, served from memory: the
        broadcasts go through, and there are no peers."""
        app.cable = type(app.cable)(cluster={"port": 9999, "peers": ["10.0.0.2:9999"]})
        app.cable.bind(app)
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        await ws.subscribe("RoomChannel", room="a")
        app.cable.broadcast("room_a", {"n": 1})
        assert (await ws.receive())["data"] == {"n": 1}
        assert app.cable.cluster_info() == []
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_recovery_off(self, app):
        app.cable = type(app.cable)(recovery=False)
        app.cable.bind(app)
        app.router.channels["RoomChannel"] = RoomChannel
        ws, task = await open_ws(app)
        confirm = await ws.subscribe("RoomChannel", room="a")
        assert confirm["positions"] == {"room_a": None}
        app.cable.broadcast("room_a", {"n": 1})
        frame = await ws.receive()
        assert "e" not in frame
        confirm = await ws.subscribe("RoomChannel", positions={"room_a": {"e": "0000abcd", "o": 0}}, room="a")
        assert confirm["recovered"] is None
        await ws.close()
        await task


# --- The handshake as the channel's request ---


class HandshakeChannel(Channel):
    captured: dict = {}

    def subscribed(self):
        request = self.request
        self.captured.update(
            path=request.path, query=dict(request.query),
            authorization=request.headers.get("authorization"),
            remote_ip=request.remote_ip, cookie=request.headers.get("cookie"),
        )


class TestHandshakeRequest:
    @pytest.mark.asyncio
    async def test_the_channel_sees_the_handshake(self, app):
        """Path and query string, `Authorization`, `X-Forwarded-For` and the
        client's address, as a controller would see them."""
        HandshakeChannel.captured = {}
        app.router.channels["HandshakeChannel"] = HandshakeChannel
        client = TestClient(app)
        client.default_headers["authorization"] = "Bearer abc"
        client.default_headers["x-forwarded-for"] = "203.0.113.9"
        client.default_headers["cookie"] = "a=1"
        ws = client.websocket("/cable?room=7&x=y")
        task = await ws.connect()
        await ws.subscribe("HandshakeChannel")
        await ws.close()
        await task
        assert HandshakeChannel.captured == {
            "path": "/cable", "query": {"room": "7", "x": "y"},
            "authorization": "Bearer abc", "remote_ip": "203.0.113.9", "cookie": "a=1",
        }

    @pytest.mark.asyncio
    async def test_without_details(self, app):
        """A bare handshake: `CABLE_PATH`, no headers, the peer's address."""
        HandshakeChannel.captured = {}
        app.router.channels["HandshakeChannel"] = HandshakeChannel
        ws, task = await open_ws(app)
        await ws.subscribe("HandshakeChannel")
        await ws.close()
        await task
        assert HandshakeChannel.captured == {
            "path": "/cable", "query": {}, "authorization": None,
            "remote_ip": "127.0.0.1", "cookie": None,
        }

    def test_the_request_built_from_details(self, app):
        from proper.channels.cable import _handshake_request

        request = _handshake_request(app, {})
        assert (request.path, request.query_string, request.client) == ("/", "", None)
        request = _handshake_request(app, {"path": "/ws?a=1", "remote_addr": "[::1]:4000"})
        assert (request.path, request.query_string, request.client) == ("/ws", "a=1", ("::1", 4000))
        assert _handshake_request(app, {"remote_addr": "nonsense"}).client is None

    @pytest.mark.asyncio
    async def test_find_session_from_a_bearer_token(self, app):
        """`find_session()` is the hook for clients without cookies."""
        class TokenChannel(FakeAuthChannel):
            def find_session(self):
                auth = self.request.headers.get("authorization", "")
                if auth.startswith("Bearer "):
                    return FakeSessionModel.find_by_token(auth.removeprefix("Bearer "))
                return super().find_session()

        app.router.channels["TokenChannel"] = TokenChannel
        client = TestClient(app)
        _reset_fakes()
        client.default_headers["authorization"] = "Bearer good-token"
        ws = client.websocket()
        task = await ws.connect()
        confirm = await ws.subscribe("TokenChannel")
        assert confirm["type"] == "confirm_subscription"
        assert FakeSessionModel.find_by_token_calls == 1
        await ws.close()
        await task


# --- Presence ---


class PresenceChannel(FakeAuthChannel):
    """Tracks the room's stream; `key` and `data` from params, for the tests
    only (an app must never take the key from params)."""

    def subscribed(self):
        stream = f"room_{self.params['room']}"
        self.stream_from(stream)
        if self.params.get("track", True):
            self.track(stream, {"name": self.params.get("name", "?")}, key=self.params.get("key"))

    def rename(self, data):
        self.update_presence({"name": data["name"]})

    def leave(self, data):
        self.untrack(f"room_{self.params['room']}")


def presence_frame(frame: dict) -> tuple:
    assert frame["c"] == "WSE"
    return frame["t"], frame["p"]["topic"], frame["p"]["user_id"], frame["p"]["data"]


async def subscribe_tracked(ws, **params) -> tuple[dict, list]:
    """Subscribe, and return the confirmation and the frames before it: the
    presence events the server writes while `subscribed()` runs come first,
    as they go straight to the connection."""
    before = []
    frame = await ws.subscribe("PresenceChannel", **params)
    while frame["type" if "type" in frame else "t"] != "confirm_subscription":
        before.append(frame)
        frame = await ws.receive()
    return frame, before


class TestPresence:
    @pytest.fixture(autouse=True)
    def _channel(self, app):
        _reset_fakes()
        app.router.channels["PresenceChannel"] = PresenceChannel

    @pytest.mark.asyncio
    async def test_who_is_in_a_stream(self, app):
        """A user's first connection joins, its last one leaves; the
        confirmation lists who is there; three tabs count once."""
        ana_tab1, task1 = await open_ws(app, _cookie(app, "good-token"))
        confirm, before = await subscribe_tracked(ana_tab1, room="a", name="Ana")
        assert confirm["presence"] == {"room_a": {"7": {"name": "Ana"}}}
        assert [presence_frame(f) for f in before] == [("presence_join", "room_a", "7", {"name": "Ana"})]
        assert app.cable.presence("room_a") == {"7": {"data": {"name": "Ana"}, "connections": 1}}

        ana_tab2, task2 = await open_ws(app, _cookie(app, "good-token"))
        confirm, before = await subscribe_tracked(ana_tab2, room="a", name="Ana")
        assert confirm["presence"] == {"room_a": {"7": {"name": "Ana"}}}
        assert before == []  # no second join
        await nothing_more(ana_tab1)
        assert app.cable.presence_stats("room_a") == {"users": 1, "connections": 2}

        # An anonymous visitor gets a key of their own
        guest, task3 = await open_ws(app)
        confirm, before = await subscribe_tracked(guest, room="a", name="Guest")
        (guest_key,) = [k for k in confirm["presence"]["room_a"] if k != "7"]
        assert guest_key.startswith("anon:")
        assert presence_frame(await ana_tab1.receive()) == ("presence_join", "room_a", guest_key, {"name": "Guest"})

        # Only the last connection of a user leaves
        await ana_tab2.close()
        await task2
        await nothing_more(guest)
        await ana_tab1.close()
        await task1
        assert presence_frame(await guest.receive()) == ("presence_leave", "room_a", "7", {"name": "Ana"})
        assert app.cable.presence("room_a") == {guest_key: {"data": {"name": "Guest"}, "connections": 1}}
        await guest.close()
        await task3
        assert app.cable.presence("room_a") == {}

    @pytest.mark.asyncio
    async def test_update_and_untrack(self, app):
        ana, task = await open_ws(app, _cookie(app, "good-token"))
        await subscribe_tracked(ana, room="a", name="Ana")
        watcher, task2 = await open_ws(app)
        await subscribe_tracked(watcher, room="a", track=False)

        # Someone else, elsewhere: Ana's update doesn't touch room_b
        bot, task3 = await open_ws(app)
        await subscribe_tracked(bot, room="b", name="Bot", key="bot")

        reply = await ana.perform("PresenceChannel", "rename", {"name": "Anna"}, room="a", name="Ana")
        assert reply["status"] == "ok"
        assert presence_frame(await watcher.receive()) == ("presence_update", "room_a", "7", {"name": "Anna"})
        await nothing_more(bot)
        # Leaving where one was never listed does nothing
        await watcher.perform("PresenceChannel", "leave", {}, room="a", track=False)
        await nothing_more(watcher)

        await ana.perform("PresenceChannel", "leave", {}, room="a", name="Ana")
        assert presence_frame(await watcher.receive()) == ("presence_leave", "room_a", "7", {"name": "Anna"})
        assert app.cable.presence("room_a") == {}
        # Still streaming: a broadcast reaches her (`perform()` skipped her
        # own presence frames)
        app.cable.broadcast("room_a", {"x": 1})
        assert (await ana.receive())["type"] == "broadcast"
        for w, tk in ((ana, task), (watcher, task2), (bot, task3)):
            await w.close()
            await tk
        # As wse: an unknown connection can't be updated
        with pytest.raises(RuntimeError, match="unknown connection"):
            app.cable.server.update_presence("nope", {})

    @pytest.mark.asyncio
    async def test_a_key_of_the_servers_choosing(self, app):
        """A custom key, the same for every stream of the connection; a
        second one for the same connection is an error."""
        ws, task = await open_ws(app)
        confirm, _ = await subscribe_tracked(ws, room="a", name="Bot", key="bot-1")
        assert confirm["presence"] == {"room_a": {"bot-1": {"name": "Bot"}}}
        confirm, _ = await subscribe_tracked(ws, room="c", name="Bot", key="bot-1")
        assert confirm["presence"] == {"room_c": {"bot-1": {"name": "Bot"}}}
        rejection = await ws.subscribe("PresenceChannel", room="b", name="Bot", key="bot-2")
        assert rejection["type"] == "reject_subscription" and rejection["reason"] == "error"
        assert app.cable.presence("room_b") == {}
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_track_needs_the_stream_and_update_needs_a_track(self, app):
        class Bad(Channel):
            def subscribed(self):
                if self.params.get("update"):
                    self.update_presence({"a": 1})
                else:
                    self.track("nowhere")

        app.router.channels["Bad"] = Bad
        ws, task = await open_ws(app)
        with pytest.raises(ValueError, match="stream_from"):
            Bad(app, {}, _send=lambda m: None).track("nowhere")
        for params in ({}, {"update": True}):
            rejection = await ws.subscribe("Bad", **params)
            assert rejection["type"] == "reject_subscription" and rejection["reason"] == "error"
        await ws.close()
        await task

    @pytest.mark.asyncio
    async def test_presence_off(self, app):
        app.cable = type(app.cable)(presence=False)
        app.cable.bind(app)
        ws, task = await open_ws(app)
        rejection = await ws.subscribe("PresenceChannel", room="a", name="Ana")
        assert rejection["type"] == "reject_subscription"  # track() fails: not enabled
        assert app.cable.presence("room_a") == {}
        assert app.cable.presence_stats("room_a") == {"users": 0, "connections": 0}
        await ws.close()
        await task

    def test_the_base_cable_has_no_one(self):
        from proper.channels import BaseCable

        cable = BaseCable()
        channel = Channel(App("proper", {"SECRET_KEYS": [SECRET]}), {}, _send=lambda m: None)
        cable.track("s", {}, channel)
        cable.untrack("s", channel)
        cable.update_presence(channel, {})
        assert cable.presence("s") == {}
        assert cable.presence_stats("s") == {"users": 0, "connections": 0}
