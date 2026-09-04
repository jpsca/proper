import threading
import time
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


class StubChannel:
    """The cable only needs a name and a `send`, not a whole Channel."""

    channel_name = "StubChannel"

    def send(self, data):
        pass


class TestConcurrency:
    """Channels subscribe from worker threads while broadcasts are delivered
    from others. Without a lock, `_streams` loses subscriptions and raises."""

    def test_subscribing_and_unsubscribing_from_many_threads(self, fast_switching):
        cable = Cable()
        errors: list[str] = []
        lost: list[int] = []
        streams = [f"room:{n}" for n in range(3)]
        workers = 6
        rounds = 20000
        ready = threading.Barrier(workers)

        def churn(i):
            channel = StubChannel()
            ready.wait()
            for r in range(rounds):
                name = streams[r % len(streams)]
                try:
                    cable.subscribe(name, channel)
                    # A subscription must be visible the moment it is made.
                    if channel not in cable._streams.get(name, ()):
                        lost.append(i)
                    cable.unsubscribe(name, channel)
                except Exception as error:  # noqa: BLE001
                    errors.append(repr(error))
                    return

        threads = [
            threading.Thread(target=churn, args=(i,)) for i in range(workers)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert lost == []
        assert cable.streams == {}

    def test_broadcasting_while_subscriptions_change(self, fast_switching):
        cable = Cable()
        errors: list[str] = []
        stop = threading.Event()

        def churn():
            channel, _ = _make_channel()
            while not stop.is_set():
                try:
                    cable.subscribe("room", channel)
                    cable.unsubscribe("room", channel)
                except Exception as error:  # noqa: BLE001
                    errors.append(repr(error))
                    return

        def broadcast():
            while not stop.is_set():
                try:
                    cable.broadcast("room", {"tick": True})
                except Exception as error:  # noqa: BLE001
                    errors.append(repr(error))
                    return

        threads = [threading.Thread(target=churn) for _ in range(3)]
        threads += [threading.Thread(target=broadcast) for _ in range(3)]
        for thread in threads:
            thread.start()
        time.sleep(0.3)
        stop.set()
        for thread in threads:
            thread.join()

        assert errors == []

    def test_a_broadcast_does_not_hold_the_lock_while_sending(self):
        """Channel code runs outside the lock, so it can touch the cable."""
        cable = Cable()
        channel, _ = _make_channel()
        reached = []

        def send(data):
            # Re-entering the cable from a send would deadlock if the
            # broadcast still held the lock.
            cable.unsubscribe("room", channel)
            reached.append(data)

        channel.send = send
        cable.subscribe("room", channel)

        finished = threading.Event()

        def run():
            cable.broadcast("room", {"msg": "hi"})
            finished.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        assert finished.wait(timeout=2), "broadcast deadlocked while sending"
        assert reached == [{"msg": "hi"}]
        assert cable.streams == {}
