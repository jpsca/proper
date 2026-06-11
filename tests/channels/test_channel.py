import typing as t

from proper.app import App
from proper.channels import Cable, Channel
from proper.helpers import DotDict


class FakeApp:
    def __init__(self):
        self.config = DotDict({"SECRET_KEYS": ["*" * 50], "DEBUG": False})
        self.cable = Cable()


def _make_channel(cls=Channel, params=None, app=None):
    app = t.cast(App, app or FakeApp())
    params = params or {}
    sent = []

    def send(msg):
        sent.append(msg)

    ch = cls(app, params, _send=send)
    return ch, sent



class TestChannel:
    def test_stores_app_and_params(self):
        app = FakeApp()
        ch, _ = _make_channel(app=app, params={"room": "general"})
        assert ch.app is app
        assert ch.params == {"room": "general"}

    def test_starts_with_no_streams(self):
        ch, _ = _make_channel()
        assert ch._streams == set()

    def test_not_rejected_by_default(self):
        ch, _ = _make_channel()
        assert ch._rejected is False

    def test_scope_none_by_default(self):
        ch, _ = _make_channel()
        assert ch.scope is None

    def test_stores_scope(self):
        app = FakeApp()
        scope = {"type": "websocket", "app": app}
        ch = Channel(t.cast(App, app), {}, scope=scope, _send=lambda _msg: None)
        assert ch.scope is scope

    def test_request_falls_back_when_scope_is_none(self):
        ch, _ = _make_channel()
        assert ch.scope is None
        assert ch.request is not None

    def test_returns_class_name(self):
        ch, _ = _make_channel()
        assert ch.channel_name == "Channel"

    def test_returns_subclass_name(self):
        class ChatChannel(Channel):
            pass

        ch, _ = _make_channel(cls=ChatChannel)
        assert ch.channel_name == "ChatChannel"



class TestStream:
    def test_adds_stream(self):
        ch, _ = _make_channel()
        ch.stream_from("chat_general")
        assert "chat_general" in ch._streams

    def test_multiple_streams(self):
        ch, _ = _make_channel()
        ch.stream_from("chat_general")
        ch.stream_from("chat_random")
        assert ch._streams == {"chat_general", "chat_random"}

    def test_idempotent(self):
        ch, _ = _make_channel()
        ch.stream_from("chat_general")
        ch.stream_from("chat_general")
        assert len(ch._streams) == 1

    def test_removes_stream(self):
        ch, _ = _make_channel()
        ch.stream_from("chat_general")
        ch.stop_stream_from("chat_general")
        assert ch._streams == set()

    def test_noop_if_not_subscribed(self):
        ch, _ = _make_channel()
        ch.stop_stream_from("nonexistent")
        assert ch._streams == set()



class TestSend:
    def test_sends_message_to_connection(self):
        ch, sent = _make_channel(params={"room": "general"})
        ch.send({"text": "hello"})
        assert len(sent) == 1
        assert sent[0] == {
            "type": "message",
            "channel": "Channel",
            "params": {"room": "general"},
            "data": {"text": "hello"},
        }

    def test_sends_multiple_messages(self):
        ch, sent = _make_channel()
        ch.send({"a": 1})
        ch.send({"b": 2})
        assert len(sent) == 2

    def test_sets_rejected_flag(self):
        ch, _ = _make_channel()
        ch.reject()
        assert ch._rejected is True



class TestLifecycleDefaults:
    def test_subscribed_is_noop(self):
        ch, _ = _make_channel()
        ch.subscribed()

    def test_unsubscribed_is_noop(self):
        ch, _ = _make_channel()
        ch.unsubscribed()



class TestDispatch:
    def test_calls_action_method_with_data(self):
        called = []

        class TestChannel(Channel):
            def speak(self, data):
                called.append(data)

        ch, _ = _make_channel(cls=TestChannel)
        ch._dispatch("speak", {"message": "hi"})
        assert called == [{"message": "hi"}]

    def test_calls_action_without_data(self):
        called = []

        class TestChannel(Channel):
            def subscribed(self):
                called.append("subscribed")

        ch, _ = _make_channel(cls=TestChannel)
        ch._dispatch("subscribed")
        assert called == ["subscribed"]



class TestUsagePattern:
    def test_chat_channel_pattern(self):
        class ChatChannel(Channel):
            def subscribed(self):
                self.stream_from(f"chat_{self.params['room']}")

            def unsubscribed(self):
                self.stop_stream_from(f"chat_{self.params['room']}")

            def speak(self, data):
                self.send({
                    "message": data["message"],
                    "room": self.params["room"],
                })

        ch, sent = _make_channel(cls=ChatChannel, params={"room": "general"})

        ch._dispatch("subscribed")
        assert "chat_general" in ch._streams

        ch._dispatch("speak", {"message": "hello"})
        assert len(sent) == 1
        assert sent[0]["data"] == {"message": "hello", "room": "general"}

        ch._dispatch("unsubscribed")
        assert ch._streams == set()

    def test_auth_rejection_pattern(self):
        class PrivateChannel(Channel):
            def subscribed(self):
                if not self.params.get("token"):
                    self.reject()
                    return
                self.stream_from("private")

        ch, _ = _make_channel(cls=PrivateChannel, params={})
        ch._dispatch("subscribed")
        assert ch._rejected is True
        assert ch._streams == set()

        ch2, _ = _make_channel(
            cls=PrivateChannel, params={"token": "valid"}
        )
        ch2._dispatch("subscribed")
        assert ch2._rejected is False
        assert "private" in ch2._streams



class TestSessionResolution:
    def test_session_none_by_default(self):
        assert Channel.Session is None

    def test_no_session_model_is_anonymous(self):
        ch, _ = _make_channel()
        assert ch._find_session_by_cookie() is None
        assert ch._resume_session() is None
