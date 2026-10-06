"""Streams on the cable: `send()` and broadcasts, and subscriptions changing
from many threads at once."""
import json
import threading
import time
import typing as t

from proper import App, Channel, current
from proper.helpers import DotDict


SECRET = "*" * 50


class FakeApp:
    def __init__(self):
        self.config = DotDict({"SECRET_KEYS": [SECRET], "DEBUG": False})


def _wse_app():
    app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {"type": "proper.channels.Cable"}})
    current.app = app
    return app


def _frames(server, conn_id):
    frames = server.frames(conn_id)
    out = []
    while not frames.empty():
        out.append(json.loads(frames.get_nowait()))
    return out


class TestSendIsForThisConnectionOnly:
    """`send()` is how a channel messages its own connection. A broadcast
    doesn't go through it: every subscriber gets the same frame (Cable
    can't call Python per subscriber)."""

    def test_a_broadcast_skips_an_overridden_send(self):
        class Filtering(Channel):
            def subscribed(self):
                self.stream_from("chat")

            def send(self, data):
                raise AssertionError("a broadcast must not call send()")

        app = _wse_app()
        app.router.channels["Filtering"] = Filtering
        server = app.cable.serve_in_memory()
        conn_id = server.connect()
        server.client_send(conn_id, '{"command": "subscribe", "channel": "Filtering"}')
        _frames(server, conn_id)  # the confirmation

        app.cable.broadcast("chat", {"msg": "hi"})

        [frame] = _frames(server, conn_id)
        assert (frame["type"], frame["stream"], frame["data"]) == ("broadcast", "chat", {"msg": "hi"})
        app.cable.stop_server()

    def test_a_direct_send_uses_the_override(self):
        sent = []

        class Upper(Channel):
            def send(self, data):
                super().send(data.upper())

        Upper(t.cast(App, FakeApp()), {}, _send=sent.append).send("hi")
        assert sent[0]["data"] == "HI"


class TestWithoutWebSockets:
    def test_a_channel_on_a_cable_without_websockets_streams_nothing(self):
        app = App("proper", {"SECRET_KEYS": [SECRET]})
        channel = Channel(app, {}, _send=[].append)
        channel.stream_from("chat")
        channel.stream_from("room")
        assert app.cable.streams == {}
        channel.stop_all_streams()
        assert channel._streams == set()


class TestConcurrency:
    """Channels subscribe and unsubscribe from worker threads while
    broadcasts are made from others. The count of channels of each connection
    streaming each stream has to stay right."""

    def _connections(self, app, count):
        server = app.cable.serve_in_memory()
        conns = []
        for _ in range(count):
            conn = app.cable._connections[server.connect()]
            conns.append((conn, Channel(app, {}, _send=conn.put, _connection=conn)))
        return server, conns

    def test_subscribing_and_unsubscribing_from_many_threads(self, fast_switching):
        app = _wse_app()
        workers = 6
        server, conns = self._connections(app, workers)
        cable = app.cable
        errors: list[str] = []
        lost: list[int] = []
        streams = [f"room:{n}" for n in range(3)]
        rounds = 5000
        ready = threading.Barrier(workers)

        def churn(i):
            conn, channel = conns[i]
            ready.wait()
            for r in range(rounds):
                name = streams[r % len(streams)]
                try:
                    channel.stream_from(name)
                    # A subscription must be visible the moment it is made.
                    if conn.conn_id not in server._topics.get(name, ()):
                        lost.append(i)
                    channel.stop_stream_from(name)
                except Exception as error:  # noqa: BLE001
                    errors.append(repr(error))
                    return

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert lost == []
        assert cable.streams == {}
        assert all(not conn_ids for conn_ids in server._topics.values())
        cable.stop_server()

    def test_broadcasting_while_subscriptions_change(self, fast_switching):
        app = _wse_app()
        server, conns = self._connections(app, 3)
        cable = app.cable
        errors: list[str] = []
        stop = threading.Event()

        def churn(channel):
            while not stop.is_set():
                try:
                    channel.stream_from("room")
                    channel.stop_stream_from("room")
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

        threads = [threading.Thread(target=churn, args=(channel,)) for _, channel in conns]
        threads += [threading.Thread(target=broadcast) for _ in range(3)]
        for thread in threads:
            thread.start()
        time.sleep(0.3)
        stop.set()
        for thread in threads:
            thread.join()

        assert errors == []
        assert cable.streams == {}
        cable.stop_server()
