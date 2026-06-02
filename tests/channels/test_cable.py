import typing as t

from proper.app import App
from proper.channels import Cable, Channel
from proper.helpers import DotDict


class FakeApp:
    def __init__(self):
        self.config = DotDict({"SECRET_KEYS": ["*" * 50], "DEBUG": False})
        self.cable = Cable()


def _make_channel(app=None, params=None):
    app = t.cast(App, app or FakeApp())
    params = params or {}
    sent = []

    def send(msg):
        sent.append(msg)

    ch = Channel(app, params, _send=send)
    return ch, sent



class TestCableInit:
    def test_starts_empty(self):
        cable = Cable()
        assert cable.streams == {}


class TestSubscribe:
    def test_adds_channel_to_stream(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        assert cable.streams == {"chat": 1}

    def test_multiple_channels_same_stream(self):
        cable = Cable()
        ch1, _ = _make_channel()
        ch2, _ = _make_channel()
        cable.subscribe("chat", ch1)
        cable.subscribe("chat", ch2)
        assert cable.streams == {"chat": 2}

    def test_same_channel_multiple_streams(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.subscribe("notifications", ch)
        assert cable.streams == {"chat": 1, "notifications": 1}

    def test_idempotent(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.subscribe("chat", ch)
        assert cable.streams == {"chat": 1}


class TestUnsubscribe:
    def test_removes_channel_from_stream(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.unsubscribe("chat", ch)
        assert cable.streams == {}

    def test_noop_if_stream_does_not_exist(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.unsubscribe("nonexistent", ch)
        assert cable.streams == {}

    def test_noop_if_channel_not_in_stream(self):
        cable = Cable()
        ch1, _ = _make_channel()
        ch2, _ = _make_channel()
        cable.subscribe("chat", ch1)
        cable.unsubscribe("chat", ch2)
        assert cable.streams == {"chat": 1}

    def test_cleans_up_empty_streams(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.unsubscribe("chat", ch)
        assert "chat" not in cable._streams


class TestUnsubscribeAll:
    def test_removes_from_all_streams(self):
        cable = Cable()
        ch, _ = _make_channel()
        cable.subscribe("chat", ch)
        cable.subscribe("notifications", ch)
        cable.unsubscribe_all(ch)
        assert cable.streams == {}

    def test_does_not_affect_other_channels(self):
        cable = Cable()
        ch1, _ = _make_channel()
        ch2, _ = _make_channel()
        cable.subscribe("chat", ch1)
        cable.subscribe("chat", ch2)
        cable.unsubscribe_all(ch1)
        assert cable.streams == {"chat": 1}


class TestBroadcast:
    def test_sends_to_all_subscribers(self):
        app = FakeApp()
        ch1, sent1 = _make_channel(app=app)
        ch2, sent2 = _make_channel(app=app)
        app.cable.subscribe("chat", ch1)
        app.cable.subscribe("chat", ch2)

        app.cable.broadcast("chat", {"text": "hello"})

        assert len(sent1) == 1
        assert sent1[0]["data"] == {"text": "hello"}
        assert len(sent2) == 1
        assert sent2[0]["data"] == {"text": "hello"}

    def test_does_not_send_to_other_streams(self):
        app = FakeApp()
        ch1, sent1 = _make_channel(app=app)
        ch2, sent2 = _make_channel(app=app)
        app.cable.subscribe("chat", ch1)
        app.cable.subscribe("notifications", ch2)

        app.cable.broadcast("chat", {"text": "hello"})

        assert len(sent1) == 1
        assert len(sent2) == 0

    def test_noop_if_no_subscribers(self):
        cable = Cable()
        cable.broadcast("empty_stream", {"text": "hello"})

    def test_error_in_one_send_does_not_break_others(self):
        app = FakeApp()

        def bad_send(msg):
            raise RuntimeError("broken")

        ch_bad = Channel(app, {}, _send=bad_send)
        ch_good, sent_good = _make_channel(app=app)

        app.cable.subscribe("chat", ch_bad)
        app.cable.subscribe("chat", ch_good)

        app.cable.broadcast("chat", {"text": "hello"})

        # ch_good still received the message
        assert len(sent_good) == 1
        assert sent_good[0]["data"] == {"text": "hello"}


class TestChannelIntegration:
    def test_stream_from_registers_with_cable(self):
        app = FakeApp()
        ch, _ = _make_channel(app=app)
        ch.stream_from("chat")
        assert app.cable.streams == {"chat": 1}

    def test_stop_stream_from_unregisters(self):
        app = FakeApp()
        ch, _ = _make_channel(app=app)
        ch.stream_from("chat")
        ch.stop_stream_from("chat")
        assert app.cable.streams == {}

    def test_stop_all_streams(self):
        app = FakeApp()
        ch, _ = _make_channel(app=app)
        ch.stream_from("chat")
        ch.stream_from("notifications")
        ch.stop_all_streams()
        assert app.cable.streams == {}
        assert ch._streams == set()

    def test_broadcast_from_channel(self):
        app = FakeApp()
        ch1, sent1 = _make_channel(app=app)
        ch2, sent2 = _make_channel(app=app)
        ch1.stream_from("chat")
        ch2.stream_from("chat")

        ch1.broadcast("chat", {"text": "hello from ch1"})

        assert len(sent1) == 1
        assert len(sent2) == 1
        assert sent1[0]["data"] == {"text": "hello from ch1"}
        assert sent2[0]["data"] == {"text": "hello from ch1"}

    def test_full_lifecycle(self):
        """stream_from -> broadcast -> stop_stream_from -> broadcast again"""
        app = FakeApp()
        ch1, sent1 = _make_channel(app=app)
        ch2, sent2 = _make_channel(app=app)

        ch1.stream_from("chat")
        ch2.stream_from("chat")

        app.cable.broadcast("chat", {"msg": "first"})
        assert len(sent1) == 1
        assert len(sent2) == 1

        ch1.stop_stream_from("chat")

        app.cable.broadcast("chat", {"msg": "second"})
        assert len(sent1) == 1  # ch1 didn't get it
        assert len(sent2) == 2  # ch2 did
