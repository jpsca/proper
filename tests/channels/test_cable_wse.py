"""Cable against a real proper-wse server. Skipped without `wse_server`."""
import base64
import errno
import http.client
import json
import logging
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import time

import pytest

from proper import App, Channel, current
from proper.channels import base as base_module
from proper.channels import cable as cable_module
from proper.helpers import BLUEPRINTS


wse_server = pytest.importorskip("wse_server")

SECRET = "*" * 50
# How long a test waits for what it expects: only an upper bound, reached
# when something is wrong (or the machine is very busy), never waited out.
TIMEOUT = 15


class WsClient:
    """A minimal WebSocket client (RFC 6455): text frames only."""

    host = "127.0.0.1"  # it connects to the first address: the one wse listens on
    read_pause = 0.0  # seconds it waits after each read from the socket

    def __init__(
        self, port, cookie="", origin=None, expect=101, rcvbuf=None, path="/cable", headers=(),
    ):
        first = socket.getaddrinfo(self.host, port, type=socket.SOCK_STREAM)[0]
        self.sock = socket.socket(first[0])
        if rcvbuf:  # a client that reads slowly: the server's writes back up
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        self.sock.settimeout(TIMEOUT)
        self.sock.connect(first[4])
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
            + (f"Cookie: {cookie}\r\n" if cookie else "")
            + (f"Origin: {origin}\r\n" if origin else "")
            + "".join(f"{name}: {value}\r\n" for name, value in headers)
            + "\r\n"
        )
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(1)
            if not chunk:
                break
            response += chunk
        self.status = int(response.split(b" ", 2)[1]) if response else 0
        assert self.status == expect, response
        self.buffer = b""

    def send_text(self, text: str):
        payload = text.encode()
        mask = os.urandom(4)
        header = bytes([0x81])
        if len(payload) < 126:
            header += bytes([0x80 | len(payload)])
        else:
            header += bytes([0x80 | 126]) + struct.pack(">H", len(payload))
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, data: dict):
        self.send_text(json.dumps(data))

    def _read(self, n):
        while len(self.buffer) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buffer += chunk
            if self.read_pause:
                time.sleep(self.read_pause)
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def recv(self, pings=False) -> dict | None:
        """The next text frame, as JSON; `None` once the server closes. wse
        pings every `CABLE_PING_INTERVAL` seconds, between any two frames:
        its pings are skipped, unless `pings`."""
        while True:
            try:
                head = self._read(2)
            except (ConnectionError, OSError):
                return None
            length = head[1] & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(length)
            opcode = head[0] & 0x0F
            if opcode == 0x8:
                # Answer the close, as browsers do: the server waits for it.
                self.sock.sendall(bytes([0x88, 0x80]) + os.urandom(4))
                self.sock.close()
                return None
            if opcode == 0x1:
                msg = json.loads(payload)
                if pings or not (msg.get("c") == "WSE" and msg.get("t") == "ping"):
                    return msg

    def recv_type(self, kind):
        while True:
            msg = self.recv()
            if msg is None or msg.get("type") == kind:
                return msg

    def subscribe(self, room):
        self.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": room}})
        return self.recv_type("confirm_subscription")

    def close(self):
        self.sock.close()


class LocalhostClient(WsClient):
    host = "localhost"


class FakeUser:
    def __init__(self, id):
        self.id = id


class FakeSession:
    def __init__(self, user):
        self.user = user
        self.user_id = user.id

    def touch(self):
        pass


class FakeSessionModel:
    @classmethod
    def find_by_token(cls, token):
        return FakeSession(FakeUser(7)) if token == "good" else None


EVENTS: list = []


class HandshakeChannel(Channel):
    captured: dict = {}

    def subscribed(self):
        request = self.request
        HandshakeChannel.captured = {
            "path": request.path, "query": dict(request.query),
            "authorization": request.headers.get("authorization"),
            "remote_ip": request.remote_ip,
        }
        self.send({"ok": True})


class PresenceChannel(Channel):
    Session = FakeSessionModel

    def find_user(self, user_id):
        return FakeUser(user_id)

    def subscribed(self):
        self.stream_from("presence:room")
        if self.params.get("track"):
            self.track("presence:room", {"name": self.params["track"]})


class LobbyChannel(Channel):
    """Streams from a room too: two channels of one connection, one stream."""

    def subscribed(self):
        self.stream_from(f"room:{self.params['room']}")


class RoomChannel(Channel):
    Session = FakeSessionModel

    def find_user(self, user_id):
        return FakeUser(user_id)

    def subscribed(self):
        if not self.authenticated or self.params.get("room") == "closed":
            return self.reject()
        EVENTS.append(("subscribed", self.params["room"]))
        self.stream_from(f"room:{self.params['room']}")
        self.send({"hello": current.user.id})

    def unsubscribed(self):
        EVENTS.append(("unsubscribed", self.params["room"]))
        if self.params["room"] == "fragile":
            raise ValueError("unsubscribed failed")

    def explode(self, data):
        raise ValueError("the action failed")

    def speak(self, data):
        self.broadcast(f"room:{self.params['room']}", {"said": data["text"]})

    def count(self, data):
        self.send({"n": data["n"]})


def _free_ports():
    """A WebSocket port whose next one (the forwarding port) is free too."""
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1", port + 1))
            return port
        except OSError:
            continue


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _config(port, **extra):
    return {
        "SECRET_KEYS": [SECRET],
        "CABLE_PORT": port,
        "CABLE": {"type": "proper.channels.Cable", "host": "127.0.0.1"},
        **extra,
    }


def _new_app(port, cable=None, **extra):
    config = _config(port, **extra)
    config["CABLE"] = {**config["CABLE"], **(cable or {})}
    app = App("proper", config)
    app.router.channels["RoomChannel"] = RoomChannel
    app.router.channels["LobbyChannel"] = LobbyChannel
    app.router.channels["HandshakeChannel"] = HandshakeChannel
    app.router.channels["PresenceChannel"] = PresenceChannel
    return app


@pytest.fixture()
def make_app():
    apps = []

    def make(cable=None, **extra):
        app = _new_app(_free_ports(), cable, **extra)
        current.app = app
        app.cable.start_server()  # returns once the server listens
        apps.append(app)
        return app

    EVENTS.clear()
    yield make
    for app in apps:
        app.cable.stop_server()


@pytest.fixture()
def wse_app(make_app):
    return make_app()


def _cookie(app, token="good"):
    return "_auth=" + app.dumps(token, salt="auth cookie")


def _wait(predicate, timeout=TIMEOUT):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class TestWseCable:
    def test_subscribe_receive_and_broadcast(self, wse_app):
        a = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        b = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        for client in (a, b):
            client.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": 1}})
            assert client.recv() == {
                "type": "message", "channel": "RoomChannel", "params": {"room": 1},
                "data": {"hello": 7},
            }
            confirm = client.recv_type("confirm_subscription")
            assert confirm["streams"] == ["room:1"]

        a.send({"command": "message", "channel": "RoomChannel", "params": {"room": 1},
                "action": "speak", "data": {"text": "hi"}})
        for client in (a, b):
            msg = client.recv_type("broadcast")
            assert msg["stream"] == "room:1"
            assert msg["data"] == {"said": "hi"}

        wse_app.cable.broadcast("room:1", {"from": "controller"})
        assert b.recv_type("broadcast")["data"] == {"from": "controller"}
        a.close()
        b.close()

    def test_rejections(self, wse_app):
        anonymous = WsClient(wse_app.config.CABLE_PORT)
        anonymous.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": 1}})
        assert anonymous.recv_type("reject_subscription")["channel"] == "RoomChannel"
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": "closed"}})
        assert client.recv_type("reject_subscription")["params"] == {"room": "closed"}
        client.send({"command": "subscribe", "channel": "Nope"})
        assert client.recv_type("reject_subscription")["reason"] == "unknown_channel"
        anonymous.close()
        client.close()

    def test_protocol_errors(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        message = {"command": "message", "channel": "RoomChannel", "params": {"room": 1}}

        client.send_text("not json")
        assert client.recv_type("error")["reason"] == "invalid_json"
        client.send_text("[1, 2]")
        assert client.recv_type("error")["reason"] == "invalid_message"
        client.send({"command": "dance"})
        assert client.recv_type("error")["reason"] == "unknown_command"
        client.send({**message, "action": "speak"})
        assert client.recv_type("error")["reason"] == "not_subscribed"

        client.subscribe(1)
        for action in ("", "_private", "broadcast", "stream_from"):
            client.send({**message, "action": action})
            assert client.recv_type("error")["reason"] == "invalid_action"
        client.send({**message, "action": "fly"})
        assert client.recv_type("error")["reason"] == "unknown_action"
        client.close()

    def test_messages_of_a_connection_keep_their_order(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        for n in range(100):
            client.send({"command": "message", "channel": "RoomChannel", "params": {"room": 1},
                         "action": "count", "data": {"n": n}})
        got = [client.recv_type("message")["data"]["n"] for _ in range(100)]
        assert got == list(range(100))
        client.close()

    def test_subscribed_and_unsubscribed_run_once_each(self, wse_app):
        """What a presence channel counts on, however the connection ends."""
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        client.subscribe(2)
        client.send({"command": "unsubscribe", "channel": "RoomChannel", "params": {"room": 1}})
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        client.sock.close()  # no close frame: the client just vanished
        assert _wait(lambda: ("unsubscribed", 2) in EVENTS)
        assert _wait(lambda: wse_app.cable.streams == {})
        wse_app.cable.stop_server()  # every command has run: nothing more can come
        assert sorted(EVENTS) == [
            ("subscribed", 1), ("subscribed", 2), ("unsubscribed", 1), ("unsubscribed", 2),
        ]

    def test_disconnect_a_user_and_clean_up(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(2)
        assert wse_app.cable.streams == {"room:2": 1}

        wse_app.cable.disconnect(user_id=7)
        assert client.recv_type("never") is None  # closed by the server
        assert _wait(lambda: wse_app.cable.streams == {})
        client.close()

    def test_a_client_reconnects_and_subscribes_again(self, wse_app):
        first = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        first.subscribe(4)
        wse_app.cable.disconnect(user_id=7)
        assert first.recv_type("never") is None

        again = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        assert again.subscribe(4)["streams"] == ["room:4"]
        assert _wait(lambda: wse_app.cable.streams == {"room:4": 1})
        wse_app.cable.broadcast("room:4", "back")
        assert again.recv_type("broadcast")["data"] == "back"
        again.close()

    def test_the_channel_sees_the_handshake(self, wse_app):
        """wse hands over the path, the query string, `Authorization` and
        the client's address (`handshake_details`)."""
        client = WsClient(
            wse_app.config.CABLE_PORT, path="/cable?room=7",
            headers=[("Authorization", "Bearer abc"), ("X-Forwarded-For", "203.0.113.9")],
        )
        client.send({"command": "subscribe", "channel": "HandshakeChannel", "params": {}})
        assert client.recv_type("message")["data"] == {"ok": True}
        assert HandshakeChannel.captured == {
            "path": "/cable", "query": {"room": "7"},
            "authorization": "Bearer abc", "remote_ip": "203.0.113.9",
        }
        client.close()

        plain = WsClient(wse_app.config.CABLE_PORT)
        plain.send({"command": "subscribe", "channel": "HandshakeChannel", "params": {}})
        plain.recv_type("message")
        assert HandshakeChannel.captured["remote_ip"] == "127.0.0.1"
        assert HandshakeChannel.captured["authorization"] is None
        plain.close()

    def test_presence(self, wse_app):
        """wse lists who is in a stream, under the key the cable gives the
        connection, and tells the subscribers who joins and leaves."""
        watcher = WsClient(wse_app.config.CABLE_PORT)
        watcher.send({"command": "subscribe", "channel": "PresenceChannel", "params": {}})
        assert watcher.recv_type("confirm_subscription")["presence"] == {}

        ana = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        ana.send({"command": "subscribe", "channel": "PresenceChannel", "params": {"track": "Ana"}})
        confirm = ana.recv_type("confirm_subscription")
        assert confirm["presence"] == {"presence:room": {"7": {"name": "Ana"}}}
        join = watcher.recv()
        assert (join["t"], join["p"]) == (
            "presence_join", {"topic": "presence:room", "user_id": "7", "data": {"name": "Ana"}},
        )
        assert wse_app.cable.presence("presence:room") == {"7": {"data": {"name": "Ana"}, "connections": 1}}
        assert wse_app.cable.presence_stats("presence:room") == {"users": 1, "connections": 1}

        ana.close()
        leave = watcher.recv()
        assert (leave["t"], leave["p"]["user_id"]) == ("presence_leave", "7")
        assert _wait(lambda: wse_app.cable.presence("presence:room") == {})
        watcher.close()

    def test_a_client_that_reconnects_gets_what_it_missed(self, wse_app):
        """wse stamps each broadcast with where it is in its stream, and
        sends again the ones after the position a subscribe carries."""
        first = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        assert first.subscribe(5)["positions"] == {"room:5": None}
        wse_app.cable.broadcast("room:5", {"n": 1})
        seen = first.recv_type("broadcast")
        assert seen["tp"] == "room:5" and seen["o"] == 0
        first.close()
        wse_app.cable.broadcast("room:5", {"n": 2})
        wse_app.cable.broadcast("room:5", {"n": 3})

        again = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        again.send({
            "command": "subscribe", "channel": "RoomChannel", "params": {"room": 5},
            "positions": {"room:5": {"e": seen["e"], "o": seen["o"]}},
        })
        # The missed ones may come before or after the confirmation
        frames = [again.recv() for _ in range(4)]
        kinds = [f["type"] for f in frames]
        assert sorted(kinds) == ["broadcast", "broadcast", "confirm_subscription", "message"]
        missed = [f["data"] for f in frames if f["type"] == "broadcast"]
        assert missed == [{"n": 2}, {"n": 3}]
        confirm = frames[kinds.index("confirm_subscription")]
        assert confirm["recovered"] is True
        assert confirm["positions"] == {"room:5": {"e": seen["e"], "o": 2}}

        # Another epoch: nothing to send again, and the current position
        again.send({
            "command": "subscribe", "channel": "RoomChannel", "params": {"room": 5},
            "positions": {"room:5": {"e": "0000abcd", "o": 0}},
        })
        confirm = again.recv_type("confirm_subscription")
        assert confirm["recovered"] is False
        assert confirm["positions"] == {"room:5": {"e": seen["e"], "o": 2}}
        again.close()

    def test_a_duplicate_subscription_streams_once(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(3)
        assert client.subscribe(3)["streams"] == ["room:3"]
        assert wse_app.cable.streams == {"room:3": 1}
        client.close()
        assert _wait(lambda: wse_app.cable.streams == {})

    def test_two_channels_of_a_connection_share_a_stream(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(5)
        client.send({"command": "subscribe", "channel": "LobbyChannel", "params": {"room": 5}})
        client.recv_type("confirm_subscription")
        assert wse_app.cable.streams == {"room:5": 2}

        client.send({"command": "unsubscribe", "channel": "LobbyChannel", "params": {"room": 5}})
        assert _wait(lambda: wse_app.cable.streams == {"room:5": 1})
        wse_app.cable.broadcast("room:5", "still here")
        assert client.recv_type("broadcast")["data"] == "still here"
        client.close()

    def test_unsubscribing_what_was_never_subscribed_does_nothing(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.send({"command": "unsubscribe", "channel": "RoomChannel", "params": {"room": 9}})
        client.subscribe(1)  # the connection still works
        assert EVENTS == [("subscribed", 1)]
        client.close()

    def test_errors_in_channel_code_are_logged_and_the_connection_goes_on(
        self, wse_app, caplog
    ):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe("fragile")
        with caplog.at_level(logging.ERROR, logger="proper"):
            client.send({"command": "message", "channel": "RoomChannel",
                         "params": {"room": "fragile"}, "action": "explode"})
            client.send({"command": "message", "channel": "RoomChannel",
                         "params": {"room": "fragile"}, "action": "count", "data": {"n": 1}})
            assert client.recv_type("message")["data"] == {"n": 1}
            client.sock.close()
            assert _wait(lambda: "unsubscribed failed" in caplog.text)
        assert "the action failed" in caplog.text
        assert _wait(lambda: wse_app.cable.streams == {})

    def test_a_connection_can_send_text_already_encoded(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT)
        assert _wait(lambda: wse_app.cable._connections)
        (conn,) = wse_app.cable._connections.values()
        conn.put('{"type": "custom"}')
        assert client.recv_type("custom") == {"type": "custom"}
        client.close()

    def test_pings_reach_every_connection(self, make_app):
        """wse pings every `CABLE_PING_INTERVAL` seconds."""
        app = make_app(CABLE_PING_INTERVAL=1)
        client = WsClient(app.config.CABLE_PORT)
        while True:
            msg = client.recv(pings=True)
            assert msg is not None, "no ping"
            if msg.get("c") == "WSE" and msg.get("t") == "ping":
                break
        client.close()


class TestLifecycle:
    def test_stop_is_clean_and_the_server_can_start_again(self, wse_app):
        port = wse_app.config.CABLE_PORT
        client = WsClient(port, _cookie(wse_app))
        client.subscribe(1)
        wse_app.cable.stop_server()
        assert not wse_app.cable.serving
        assert EVENTS == [("subscribed", 1), ("unsubscribed", 1)]  # still open: cleaned up
        assert wse_app.cable.streams == {}
        client.close()
        with socket.socket() as s:  # the forwarding port is free again
            s.bind(("127.0.0.1", port + 1))

        wse_app.cable.start_server()
        wse_app.cable.start_server()  # once is enough
        again = WsClient(port, _cookie(wse_app))
        assert again.subscribe(1)["streams"] == ["room:1"]
        again.close()

    def test_a_taken_forwarding_port_fails_before_anything_starts(self):
        port = _free_ports()
        app = _new_app(port)
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", port + 1))
            taken.listen()
            with pytest.raises(OSError):
                app.cable.start_server()
        assert not app.cable.serving
        with socket.socket() as s:  # the WebSocket port was never opened
            s.bind(("127.0.0.1", port))

    def test_start_server_returns_once_wse_listens(self):
        """wse binds its port after `start()` returns, and the drain thread,
        which hands its events to the channels, stops when wse isn't
        running: started before wse listened, it stopped at once, and no
        command was ever answered. `localhost` has to be looked up first,
        which leaves more time for that."""
        apps = []
        try:
            for _ in range(3):
                app = _new_app(_free_ports(), cable={"host": "localhost"})
                current.app = app
                app.cable.start_server()
                apps.append(app)
                assert app.cable.server.is_running()
            for app in apps:
                client = LocalhostClient(app.config.CABLE_PORT, _cookie(app))
                assert client.subscribe(1) is not None, "a cable that answers nothing"
                client.close()
        finally:  # together: each takes wse a while
            stops = [threading.Thread(target=app.cable.stop_server) for app in apps]
            for stop in stops:
                stop.start()
            for stop in stops:
                stop.join()

    def test_a_taken_websocket_port_fails_at_once_with_the_reason(self, monkeypatch):
        """wse never listens on a port it can't bind: `start_server()` raises
        as soon as wse gives up, saying why, instead of returning with a
        cable that serves nothing."""
        monkeypatch.setattr(cable_module, "START_TIMEOUT", 60.0)  # not the reason
        port = _free_ports()
        app = _new_app(port)
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", port))
            taken.listen()
            start = time.monotonic()
            with pytest.raises(RuntimeError, match=f"could not listen on 127.0.0.1:{port}: .*in use"):
                app.cable.start_server()
            assert time.monotonic() - start < TIMEOUT
        assert not app.cable.serving
        with socket.socket() as s:  # the forwarding port is free again
            s.bind(("127.0.0.1", port + 1))

    def test_a_host_that_cannot_be_found_fails_with_the_reason(self, monkeypatch):
        """Also when wse gives up after `START_TIMEOUT`: the reason is that,
        not the time."""
        monkeypatch.setattr(cable_module, "START_TIMEOUT", 0.0)
        app = _new_app(_free_ports(), cable={"host": "no-such-host.invalid"})
        with pytest.raises(RuntimeError, match="could not listen on no-such-host.invalid:"):
            app.cable.start_server()
        assert not app.cable.serving

    def test_a_server_that_listens_too_late_is_stopped(self, monkeypatch):
        """wse can't be stopped before it has bound its port: one that binds
        after `START_TIMEOUT` is waited for and stopped, so nothing is left
        listening, and the next start can bind the port. `localhost` has to
        be looked up first, so with no time at all most starts are late."""
        monkeypatch.setattr(cable_module, "START_TIMEOUT", 0.0)
        for _ in range(20):
            port = _free_ports()
            app = _new_app(port, cable={"host": "localhost"})
            current.app = app
            try:
                app.cable.start_server()
            except RuntimeError as error:
                late = f"took more than 0.0 seconds to listen on localhost:{port}"
                assert late in str(error)
                break
            app.cable.stop_server()  # in time: try again
        else:
            pytest.fail("wse was never late")
        assert not app.cable.serving
        for family, kind, _, _, address in socket.getaddrinfo("localhost", port, type=socket.SOCK_STREAM):
            with socket.socket(family, kind) as s:
                assert s.connect_ex(address) != 0, f"{address} still listening"
        monkeypatch.setattr(cable_module, "START_TIMEOUT", 10.0)
        app.cable.start_server()  # again, on the same port
        assert app.cable.serving
        app.cable.stop_server()

    def test_the_reason_a_port_cannot_be_listened_on(self):
        port = _free_port()
        assert cable_module._bind_error("127.0.0.1", port) is None
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", port))
            taken.listen()
            assert cable_module._bind_error("127.0.0.1", port).errno == errno.EADDRINUSE

    def test_a_server_that_fails_to_build_leaves_the_forwarding_port_free(self):
        port = _free_ports()
        app = App("proper", {**_config(port), "CABLE": {
            "type": "proper.channels.Cable", "host": "127.0.0.1", "bogus": 1,
        }})
        with pytest.raises(TypeError):
            app.cable.start_server()
        with socket.socket() as s:
            s.bind(("127.0.0.1", port + 1))

    def test_a_cable_serving_on_a_port_cannot_serve_from_memory(self, wse_app):
        with pytest.raises(RuntimeError, match="already serving"):
            wse_app.cable.serve_in_memory()

    def test_stopping_a_cable_that_never_started_does_nothing(self):
        app = _new_app(_free_ports())
        app.cable.stop_server()
        assert not app.cable.serving

    def test_a_port_is_required(self):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {"type": "proper.channels.Cable"}})
        with pytest.raises(RuntimeError, match="CABLE_PORT"):
            app.cable.start_server()

    def test_the_original_wse_server_is_refused(self, monkeypatch):
        class OriginalWseServer:  # what wse-server 2.4 lacks: topic_backlog
            def __init__(self, *args, **kwargs):
                pass

        monkeypatch.setattr(wse_server, "RustWSEServer", OriginalWseServer)
        app = _new_app(_free_ports())
        with pytest.raises(RuntimeError, match="proper-wse"):
            app.cable.start_server()
        assert not app.cable.serving

    def test_unknown_server_options_are_not_swallowed(self):
        app = App("proper", {**_config(_free_ports()), "CABLE": {
            "type": "proper.channels.Cable", "host": "127.0.0.1", "bogus": 1,
        }})
        with pytest.raises(TypeError, match="bogus"):
            app.cable.start_server()

    def test_a_broadcast_with_nowhere_to_go_is_logged(self, caplog):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {"type": "proper.channels.Cable"}})
        with caplog.at_level(logging.WARNING, logger="proper"):
            app.cable.broadcast("room:1", "lost")
        assert "is lost" in caplog.text


class TestForwarding:
    def test_a_broadcast_from_another_process_arrives(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        code = (
            "from proper import App\n"
            f"app = App('proper', {_config(wse_app.config.CABLE_PORT)!r})\n"
            "assert not app.cable.serving\n"
            "app.cable.broadcast('room:1', {'from': 'a task'})\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True, timeout=60)
        assert client.recv_type("broadcast")["data"] == {"from": "a task"}
        client.close()

    def test_a_broadcast_answered_late_is_delivered_once(self, make_app, monkeypatch):
        """A forwarded broadcast is answered once it is delivered, and
        delivery waits while the subscribers are behind (backpressure). An
        answer later than `FORWARD_TIMEOUT` makes the sender try again, and
        the cable process must not deliver it a second time."""
        monkeypatch.setattr(base_module, "FORWARD_TIMEOUT", 0.3)
        app = make_app(cable={"backpressure_timeout": 1.0})
        port = app.config.CABLE_PORT
        stalled = WsClient(port, _cookie(app), rcvbuf=4096)  # never reads
        stalled.subscribe(1)
        reader = WsClient(port, _cookie(app))
        reader.subscribe(1)
        waits, app.cable._backpressure_bytes = app.cable._backpressure_bytes, 0
        for _ in range(10):  # a backlog, after which each broadcast waits a second
            app.cable.broadcast("room:1", BIG)
        app.cable._backpressure_bytes = waits
        got, thread = _read_all(reader, 10)
        thread.join(timeout=TIMEOUT)

        other = App("proper", _config(port))  # another process of the app
        assert not other.cable.serving
        other.cable.broadcast("room:1", "once")  # sent twice: answered late
        frames = [reader.recv_type("broadcast")["data"]]
        # A second delivery would start before this one, and wait as long:
        # wse would send it first.
        app.cable.broadcast("room:1", "last")
        while frames[-1] != "last":
            msg = reader.recv_type("broadcast")
            assert msg is not None, frames
            frames.append(msg["data"])
        assert frames == ["once", "last"]
        stalled.close()
        reader.close()

    def test_batches_and_disconnects_are_forwarded(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        elsewhere = _new_app(wse_app.config.CABLE_PORT)  # not serving: forwards

        with elsewhere.cable.batch():
            elsewhere.cable.broadcast("room:1", "one")
            elsewhere.cable.broadcast("room:1", "two")
        assert client.recv_type("broadcast")["data"] == "one"
        assert client.recv_type("broadcast")["data"] == "two"

        elsewhere.cable.disconnect(user_id=7)
        assert client.recv_type("never") is None

    def test_the_serving_process_broadcasts_directly_even_in_a_batch(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        with wse_app.cable.batch():
            wse_app.cable.broadcast("room:1", "here")
            assert client.recv_type("broadcast")["data"] == "here"
        client.close()

    @pytest.mark.parametrize("path, token, status", [
        ("/cable", "forged", 403),
        ("/elsewhere", "forged", 404),
    ])
    def test_forged_or_misdirected_broadcasts_are_refused(self, wse_app, path, token, status):
        conn = http.client.HTTPConnection("127.0.0.1", wse_app.config.CABLE_PORT + 1, timeout=TIMEOUT)
        conn.request("POST", path, body=token.encode())
        assert conn.getresponse().status == status
        conn.close()

    def test_a_forked_copy_forwards_instead_of_serving(self, wse_app):
        pid = wse_app.cable._owner_pid
        wse_app.cable._owner_pid = pid + 1  # as a fork sees it
        try:
            assert not wse_app.cable.serving
            assert wse_app.cable._forwarding
        finally:
            wse_app.cable._owner_pid = pid


BIG = "x" * 200_000


class TestBackpressure:
    def test_a_broadcast_waits_while_the_subscribers_are_behind(self, make_app):
        app = make_app(cable={"backpressure_bytes": 100_000, "backpressure_timeout": 0.5})
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        for _ in range(10):  # far more than the socket takes: a backlog
            app.cable.broadcast("room:1", BIG)
        start = time.monotonic()
        app.cable.broadcast("room:1", BIG)
        assert time.monotonic() - start >= 0.45  # waited, then sent anyway

        got = 0
        while got < 11:  # the client catches up, and the backlog with it
            got += reader.recv_type("broadcast") is not None
        # Caught up, a broadcast doesn't wait. One that waited would take
        # the whole timeout, made long so that a busy machine can't look
        # like one.
        app.cable._backpressure_timeout = 60
        start = time.monotonic()
        app.cable.broadcast("room:1", "small")
        assert time.monotonic() - start < TIMEOUT
        assert reader.recv_type("broadcast")["data"] == "small"
        reader.close()

    def test_it_can_be_turned_off(self, make_app):
        app = make_app(cable={"backpressure_bytes": 0})
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        start = time.monotonic()
        for _ in range(11):
            app.cable.broadcast("room:1", BIG)
        # Waiting, each of the last ten would take `backpressure_timeout`
        # (one second)
        assert time.monotonic() - start < 5
        reader.close()


def _read_all(client, count):
    """Read `count` broadcasts in a thread, as a live client would."""
    got = []

    def read():
        while len(got) < count:
            msg = client.recv()
            if msg is None:
                return
            if msg.get("type") == "broadcast":
                got.append(msg)

    thread = threading.Thread(target=read, daemon=True)
    thread.start()
    return got, thread


class TestStalledClients:
    """A client that stops reading is closed, and `cable.js` reconnects;
    one that reads slowly is not."""

    def _app(self, make_app, limit, stall):
        return make_app(
            cable={"backpressure_bytes": 0},  # nothing waits: the backlog stays
            CABLE_MAX_PENDING_BYTES=limit,
            CABLE_STALL_TIMEOUT=stall,
        )

    def test_nothing_through_for_the_stall_timeout(self, make_app):
        app = self._app(make_app, limit=300_000, stall=0.6)
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        for _ in range(10):  # ~2 MB: over the limit, under ten times it
            app.cable.broadcast("room:1", BIG)
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        reader.close()

    def test_ten_times_the_limit_at_any_speed(self, make_app):
        app = self._app(make_app, limit=100_000, stall=30)
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        for _ in range(10):  # ~2 MB: over ten times the limit
            app.cable.broadcast("room:1", BIG)
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        reader.close()

    def test_a_client_that_reads_slowly_stays(self, make_app):
        """wse writes to a client as it reads, in steps of about 120 KB
        (what its socket's buffer frees), and each step counts as progress.
        This client reads about 4 KB every 10 ms: more than `limit` waits
        for it for about 3.5 seconds, longer than the stall timeout, so it
        would be closed if its progress didn't count; and a step takes about
        0.3 seconds, so it would take a machine six times slower than that
        to stall it for the 2 seconds of the timeout."""
        app = self._app(make_app, limit=200_000, stall=2)
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.read_pause = 0.01
        reader.subscribe(1)
        for _ in range(9):  # 1.8 MB: under ten times the limit
            app.cable.broadcast("room:1", BIG)
        for n in range(9):
            assert reader.recv_type("broadcast") is not None, f"closed after {n} frames"
        assert ("unsubscribed", 1) not in EVENTS
        reader.close()

    def test_it_can_be_turned_off(self, make_app):
        app = make_app(CABLE_MAX_PENDING_BYTES=0)
        assert app.cable._watcher is None


class TestIdleClients:
    """wse closes a connection that sends it nothing for `idle_timeout`
    seconds. `cable.js` answers wse's pings, so a page that only listens
    stays connected."""

    def _pong(self):
        source = (BLUEPRINTS / "addon_channels/assets/js/cable.js").read_text()
        return re.search(r"const WSE_PONG = '(.+)'", source).group(1)

    def test_a_client_that_answers_the_pings_stays(self, make_app):
        """Two clients that only listen, one of which answers the pings.
        The test lasts until wse closes the silent one: by then both have
        been connected for more than `idle_timeout`, and the one that
        answers must still be open. Pings every second and an
        `idle_timeout` of 5: an answer can be about 4 seconds late (a busy
        machine) before wse takes the client for idle."""
        app = make_app(cable={"idle_timeout": 5}, CABLE_PING_INTERVAL=1)
        pong = self._pong()
        listener = WsClient(app.config.CABLE_PORT, _cookie(app))
        listener.subscribe(1)
        silent = WsClient(app.config.CABLE_PORT, _cookie(app))
        silent.subscribe(2)
        closed = threading.Event()

        def until_closed():
            silent.recv_type("never")  # `None` once wse closes it
            closed.set()

        threading.Thread(target=until_closed, daemon=True).start()
        pings = 0
        until = time.monotonic() + 5 + TIMEOUT
        while not closed.is_set():
            assert time.monotonic() < until, "wse never closed the silent client"
            msg = listener.recv(pings=True)  # one at least every second
            assert msg is not None, "the server closed a client that answers"
            if msg.get("c") == "WSE" and msg.get("t") == "ping":
                pings += 1
                listener.send_text(pong)

        assert pings > 0
        assert _wait(lambda: ("unsubscribed", 2) in EVENTS)
        listener.send({"command": "message", "channel": "RoomChannel", "params": {"room": 1},
                       "action": "count", "data": {"n": 1}})
        assert listener.recv_type("message")["data"] == {"n": 1}  # still open
        assert ("unsubscribed", 1) not in EVENTS
        listener.close()


class TestOrigins:
    def test_other_sites_pages_are_refused(self, make_app):
        app = make_app(HOST="app.example")
        port = app.config.CABLE_PORT
        WsClient(port, origin="https://evil.example", expect=403).close()
        WsClient(port, origin="https://app.example").close()
        WsClient(port).close()  # not a browser


class TestCluster:
    """Two cables, one per "machine", in wse's cluster over the loopback."""

    @pytest.fixture()
    def pair(self, make_app):
        cluster_a, cluster_b = _free_port(), _free_port()
        while cluster_b == cluster_a:
            cluster_b = _free_port()
        a = make_app(cable={"cluster": {"port": cluster_a, "peers": [f"127.0.0.1:{cluster_b}"]}})
        b = make_app(cable={"cluster": {"port": cluster_b, "peers": [f"127.0.0.1:{cluster_a}"]}})
        # a dials b before b listens and retries with a backoff; b's dial to
        # a succeeds, but each side reports the link in its own time
        assert _wait(lambda: a.cable.cluster_info() and b.cable.cluster_info()), "the cables never met"
        return a, b

    def _drain(self, client, seconds=0.5):
        """Every frame the client gets in `seconds` (`recv()` is `None` on
        the socket's timeout)."""
        client.sock.settimeout(seconds)
        frames = []
        try:
            while (frame := client.recv()) is not None:
                frames.append(frame)
        finally:
            client.sock.settimeout(TIMEOUT)
        return frames

    def _read_until(self, client, done):
        """The frames the client gets until `done(frames)`."""
        frames = []
        while not done(frames):
            frame = client.recv()
            assert frame is not None, frames
            frames.append(frame)
        return frames

    def _broadcasts(self, frames):
        return [f["data"] for f in frames if f.get("type") == "broadcast"]

    def _reach(self, cable, client, stream, data):
        """Broadcast until the client gets it: the interest of the client's
        machine takes a moment to reach the other one."""
        until = time.monotonic() + TIMEOUT
        while time.monotonic() < until:
            cable.broadcast(stream, data)
            for frame in self._drain(client, 0.4):
                if frame.get("type") == "broadcast" and frame["data"] == data:
                    return frame
        raise AssertionError(f"{data} never reached the other machine")

    def test_a_broadcast_reaches_the_other_machine(self, pair):
        a, b = pair
        client = WsClient(b.config.CABLE_PORT, _cookie(b))
        client.subscribe(1)
        from_a = self._reach(a.cable, client, "room:1", {"from": "a"})
        assert from_a["tp"] == "room:1"  # stamped by a, with a's epoch
        from_b = self._reach(b.cable, client, "room:1", {"from": "b"})
        assert from_b["e"] != from_a["e"]

        # Back with both positions: what each machine published since
        a.cable.broadcast("room:1", {"from": "a", "n": 2})
        b.cable.broadcast("room:1", {"from": "b", "n": 2})
        self._read_until(client, lambda frames: all(
            {"from": who, "n": 2} in self._broadcasts(frames) for who in "ab"
        ))  # in b's buffer
        client.close()
        again = WsClient(b.config.CABLE_PORT, _cookie(b))
        again.send({
            "command": "subscribe", "channel": "RoomChannel", "params": {"room": 1},
            "positions": {"room:1": [{"e": from_a["e"], "o": from_a["o"]}, {"e": from_b["e"], "o": from_b["o"]}]},
        })
        frames = self._read_until(again, lambda frames: any(
            f.get("type") == "confirm_subscription" for f in frames
        ) and all({"from": who, "n": 2} in self._broadcasts(frames) for who in "ab"))
        confirm = [f for f in frames if f.get("type") == "confirm_subscription"][0]
        assert confirm["recovered"] is True
        replayed = [f["data"] for f in frames if f.get("type") == "broadcast"]
        assert {"from": "a", "n": 2} in replayed
        assert {"from": "b", "n": 2} in replayed
        again.close()

    def test_presence_and_disconnect_across_machines(self, pair):
        a, b = pair
        on_a = WsClient(a.config.CABLE_PORT, _cookie(a))
        on_a.send({"command": "subscribe", "channel": "PresenceChannel", "params": {"track": "Ana"}})
        on_a.recv_type("confirm_subscription")
        assert _wait(
            lambda: b.cable.presence("presence:room") == {"7": {"data": {"name": "Ana"}, "connections": 1}},
        )

        on_b = WsClient(b.config.CABLE_PORT, _cookie(b))
        on_b.subscribe(2)
        assert _wait(lambda: b.cable.streams == {"room:2": 1})
        a.cable.disconnect(user_id=7)  # from the other machine
        assert on_a.recv_type("never") is None
        assert on_b.recv_type("never") is None
        assert _wait(
            lambda: a.cable.presence("presence:room") == {} and b.cable.presence("presence:room") == {},
        )
        assert len(a.cable.cluster_info()) == 1

    def test_health(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        assert _wait(lambda: wse_app.cable.health()["streams"] == 1)
        health = wse_app.cable.health()
        assert (health["serving"], health["connections"], health["users"]) == (True, 1, 1)
        assert health["server"]["connections"] == 1
        assert health["server"]["uptime_secs"] >= 0
        assert health["server"]["cluster_connected"] is False
        client.close()

    def test_metrics_on_the_loopback_port(self, wse_app):
        client = WsClient(wse_app.config.CABLE_PORT, _cookie(wse_app))
        client.subscribe(1)
        assert _wait(lambda: wse_app.cable.streams == {"room:1": 1})
        conn = http.client.HTTPConnection("127.0.0.1", wse_app.config.CABLE_PORT + 1, timeout=TIMEOUT)
        conn.request("GET", "/metrics")
        response = conn.getresponse()
        text = response.read().decode()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("text/plain; version=0.0.4")
        assert "# TYPE wse_connections gauge\nwse_connections 1\n" in text
        assert "wse_uptime_seconds" in text
        assert "proper_cable_streams 1\n" in text
        conn.request("GET", "/other")
        assert conn.getresponse().status == 404
        conn.close()
        client.close()

    def test_a_cluster_that_fails_to_join_leaves_nothing_behind(self):
        """A bad TLS config fails `start_server()`, and both ports are free
        for the next attempt."""
        port = _free_ports()
        app = _new_app(port, cable={"cluster": {
            "port": _free_ports(), "peers": ["127.0.0.1:1"],
            "tls": {"cert": "/nonexistent.pem", "key": "/nonexistent.key", "ca": "/nonexistent-ca.pem"},
        }})
        with pytest.raises(RuntimeError, match="TLS"):
            app.cable.start_server()
        assert not app.cable.serving
        again = _new_app(port)
        again.cable.start_server()
        again.cable.stop_server()

    def test_the_rest_ignores_the_control_topic(self, wse_app, caplog):
        cable = wse_app.cable
        assert cable.cluster_info() == []  # no cluster
        cable._control({"topic": "other", "data": "x"})
        with caplog.at_level(logging.WARNING):
            cable._control({"topic": "proper:cable:control", "data": "not json"})
        assert "isn't JSON" in caplog.text
        cable._control({"topic": "proper:cable:control", "data": "[1]"})  # not a dict: ignored
