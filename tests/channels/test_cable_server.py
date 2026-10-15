"""Cable against a real server: Bearings, on a port."""
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
from proper.helpers import BLUEPRINTS


SECRET = "*" * 50
# How long a test waits for what it expects: only an upper bound, reached
# when something is wrong (or the machine is very busy), never waited out.
TIMEOUT = 15


class WsClient:
    """A minimal WebSocket client (RFC 6455): text frames only."""

    host = "127.0.0.1"  # it connects to the first address: the one the cable listens on
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

    def send_text(self, text: str, opcode=0x1):
        payload = text.encode()
        mask = os.urandom(4)
        header = bytes([0x80 | opcode])
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
        """The next text frame, as JSON; `None` once the server closes. The
        cable pings every `CABLE_PING_INTERVAL` seconds, between any two frames:
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
def cable_app(make_app):
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


class TestCable:
    def test_subscribe_receive_and_broadcast(self, cable_app):
        a = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        b = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
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

        cable_app.cable.broadcast("room:1", {"from": "controller"})
        assert b.recv_type("broadcast")["data"] == {"from": "controller"}
        a.close()
        b.close()

    def test_rejections(self, cable_app):
        anonymous = WsClient(cable_app.config.CABLE_PORT)
        anonymous.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": 1}})
        assert anonymous.recv_type("reject_subscription")["channel"] == "RoomChannel"
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.send({"command": "subscribe", "channel": "RoomChannel", "params": {"room": "closed"}})
        assert client.recv_type("reject_subscription")["params"] == {"room": "closed"}
        client.send({"command": "subscribe", "channel": "Nope"})
        assert client.recv_type("reject_subscription")["reason"] == "unknown_channel"
        anonymous.close()
        client.close()

    def test_protocol_errors(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
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

    def test_messages_of_a_connection_keep_their_order(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        for n in range(100):
            client.send({"command": "message", "channel": "RoomChannel", "params": {"room": 1},
                         "action": "count", "data": {"n": n}})
        got = [client.recv_type("message")["data"]["n"] for _ in range(100)]
        assert got == list(range(100))
        client.close()

    def test_subscribed_and_unsubscribed_run_once_each(self, cable_app):
        """What a presence channel counts on, however the connection ends."""
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        client.subscribe(2)
        client.send({"command": "unsubscribe", "channel": "RoomChannel", "params": {"room": 1}})
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        client.sock.close()  # no close frame: the client just vanished
        assert _wait(lambda: ("unsubscribed", 2) in EVENTS)
        assert _wait(lambda: cable_app.cable.streams == {})
        cable_app.cable.stop_server()  # every command has run: nothing more can come
        assert sorted(EVENTS) == [
            ("subscribed", 1), ("subscribed", 2), ("unsubscribed", 1), ("unsubscribed", 2),
        ]

    def test_disconnect_a_user_and_clean_up(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(2)
        assert cable_app.cable.streams == {"room:2": 1}

        cable_app.cable.disconnect(user_id=7)
        assert client.recv_type("never") is None  # closed by the server
        assert _wait(lambda: cable_app.cable.streams == {})
        client.close()

    def test_a_client_reconnects_and_subscribes_again(self, cable_app):
        first = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        first.subscribe(4)
        cable_app.cable.disconnect(user_id=7)
        assert first.recv_type("never") is None

        again = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        assert again.subscribe(4)["streams"] == ["room:4"]
        assert _wait(lambda: cable_app.cable.streams == {"room:4": 1})
        cable_app.cable.broadcast("room:4", "back")
        assert again.recv_type("broadcast")["data"] == "back"
        again.close()

    def test_the_channel_sees_the_handshake(self, cable_app):
        """The channel gets the path, the query string, `Authorization` and
        the client's address of the handshake."""
        client = WsClient(
            cable_app.config.CABLE_PORT, path="/cable?room=7",
            headers=[("Authorization", "Bearer abc"), ("X-Forwarded-For", "203.0.113.9")],
        )
        client.send({"command": "subscribe", "channel": "HandshakeChannel", "params": {}})
        assert client.recv_type("message")["data"] == {"ok": True}
        assert HandshakeChannel.captured == {
            "path": "/cable", "query": {"room": "7"},
            "authorization": "Bearer abc", "remote_ip": "203.0.113.9",
        }
        client.close()

        plain = WsClient(cable_app.config.CABLE_PORT)
        plain.send({"command": "subscribe", "channel": "HandshakeChannel", "params": {}})
        plain.recv_type("message")
        assert HandshakeChannel.captured["remote_ip"] == "127.0.0.1"
        assert HandshakeChannel.captured["authorization"] is None
        plain.close()

    def test_presence(self, cable_app):
        """The cable lists who is in a stream, under the key it gives the
        connection, and tells the subscribers who joins and leaves."""
        watcher = WsClient(cable_app.config.CABLE_PORT)
        watcher.send({"command": "subscribe", "channel": "PresenceChannel", "params": {}})
        assert watcher.recv_type("confirm_subscription")["presence"] == {}

        ana = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        ana.send({"command": "subscribe", "channel": "PresenceChannel", "params": {"track": "Ana"}})
        confirm = ana.recv_type("confirm_subscription")
        assert confirm["presence"] == {"presence:room": {"7": {"name": "Ana"}}}
        join = watcher.recv()
        assert (join["t"], join["p"]) == (
            "presence_join", {"topic": "presence:room", "user_id": "7", "data": {"name": "Ana"}},
        )
        assert cable_app.cable.presence("presence:room") == {"7": {"data": {"name": "Ana"}, "connections": 1}}
        assert cable_app.cable.presence_stats("presence:room") == {"users": 1, "connections": 1}

        ana.close()
        leave = watcher.recv()
        assert (leave["t"], leave["p"]["user_id"]) == ("presence_leave", "7")
        assert _wait(lambda: cable_app.cable.presence("presence:room") == {})
        watcher.close()

    def test_a_client_that_reconnects_gets_what_it_missed(self, cable_app):
        """The cable stamps each broadcast with where it is in its stream, and
        sends again the ones after the position a subscribe carries."""
        first = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        assert first.subscribe(5)["positions"] == {"room:5": None}
        cable_app.cable.broadcast("room:5", {"n": 1})
        seen = first.recv_type("broadcast")
        assert seen["tp"] == "room:5" and seen["o"] == 0
        first.close()
        cable_app.cable.broadcast("room:5", {"n": 2})
        cable_app.cable.broadcast("room:5", {"n": 3})

        again = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
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

    def test_a_duplicate_subscription_streams_once(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(3)
        assert client.subscribe(3)["streams"] == ["room:3"]
        assert cable_app.cable.streams == {"room:3": 1}
        client.close()
        assert _wait(lambda: cable_app.cable.streams == {})

    def test_two_channels_of_a_connection_share_a_stream(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(5)
        client.send({"command": "subscribe", "channel": "LobbyChannel", "params": {"room": 5}})
        client.recv_type("confirm_subscription")
        assert cable_app.cable.streams == {"room:5": 2}

        client.send({"command": "unsubscribe", "channel": "LobbyChannel", "params": {"room": 5}})
        assert _wait(lambda: cable_app.cable.streams == {"room:5": 1})
        cable_app.cable.broadcast("room:5", "still here")
        assert client.recv_type("broadcast")["data"] == "still here"
        client.close()

    def test_unsubscribing_what_was_never_subscribed_does_nothing(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.send({"command": "unsubscribe", "channel": "RoomChannel", "params": {"room": 9}})
        client.subscribe(1)  # the connection still works
        assert EVENTS == [("subscribed", 1)]
        client.close()

    def test_errors_in_channel_code_are_logged_and_the_connection_goes_on(
        self, cable_app, caplog
    ):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
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
        assert _wait(lambda: cable_app.cable.streams == {})

    def test_a_binary_message_is_read_as_text(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.send_text(json.dumps({"command": "dance"}), opcode=0x2)
        assert client.recv_type("error")["reason"] == "unknown_command"
        client.close()

    def test_a_connection_can_send_text_already_encoded(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT)
        assert _wait(lambda: cable_app.cable._connections)
        (conn,) = cable_app.cable._connections.values()
        conn.put('{"type": "custom"}')
        assert client.recv_type("custom") == {"type": "custom"}
        client.close()

    def test_pings_reach_every_connection(self, make_app):
        """The cable pings every `CABLE_PING_INTERVAL` seconds."""
        app = make_app(CABLE_PING_INTERVAL=1)
        client = WsClient(app.config.CABLE_PORT)
        while True:
            msg = client.recv(pings=True)
            assert msg is not None, "no ping"
            if msg.get("c") == "WSE" and msg.get("t") == "ping":
                break
        client.close()


class TestLifecycle:
    def test_stop_is_clean_and_the_server_can_start_again(self, cable_app):
        port = cable_app.config.CABLE_PORT
        client = WsClient(port, _cookie(cable_app))
        client.subscribe(1)
        cable_app.cable.stop_server()
        assert not cable_app.cable.serving
        assert EVENTS == [("subscribed", 1), ("unsubscribed", 1)]  # still open: cleaned up
        assert cable_app.cable.streams == {}
        client.close()
        with socket.socket() as s:  # the forwarding port is free again
            s.bind(("127.0.0.1", port + 1))

        cable_app.cable.start_server()
        cable_app.cable.start_server()  # once is enough
        again = WsClient(port, _cookie(cable_app))
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

    def test_start_server_returns_once_it_listens(self):
        """`localhost` is looked up, and the cable listens on its first
        address, the one a client connects to."""
        app = _new_app(_free_ports(), cable={"host": "localhost"})
        current.app = app
        app.cable.start_server()
        try:
            client = LocalhostClient(app.config.CABLE_PORT, _cookie(app))
            assert client.subscribe(1) is not None, "a cable that answers nothing"
            client.close()
        finally:
            app.cable.stop_server()

    def test_a_taken_websocket_port_fails_at_once_with_the_reason(self):
        port = _free_ports()
        app = _new_app(port)
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", port))
            taken.listen()
            with pytest.raises(OSError, match="in use") as error:
                app.cable.start_server()
            assert error.value.errno == errno.EADDRINUSE
        assert not app.cable.serving
        with socket.socket() as s:  # the forwarding port is free again
            s.bind(("127.0.0.1", port + 1))

    def test_a_host_that_cannot_be_found_fails_with_the_reason(self):
        app = _new_app(_free_ports(), cable={"host": "no-such-host.invalid"})
        with pytest.raises(socket.gaierror):
            app.cable.start_server()
        assert not app.cable.serving

    def test_a_cable_serving_on_a_port_cannot_serve_from_memory(self, cable_app):
        with pytest.raises(RuntimeError, match="already serving"):
            cable_app.cable.serve_in_memory()

    def test_stopping_a_cable_that_never_started_does_nothing(self):
        app = _new_app(_free_ports())
        app.cable.stop_server()
        assert not app.cable.serving

    def test_a_port_is_required(self):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {"type": "proper.channels.Cable"}})
        with pytest.raises(RuntimeError, match="CABLE_PORT"):
            app.cable.start_server()

    def test_unknown_options_are_not_swallowed(self):
        with pytest.raises(TypeError, match="bogus"):
            App("proper", {**_config(_free_ports()), "CABLE": {
                "type": "proper.channels.Cable", "host": "127.0.0.1", "bogus": 1,
            }})

    def test_a_broadcast_with_nowhere_to_go_is_logged(self, caplog):
        app = App("proper", {"SECRET_KEYS": [SECRET], "CABLE": {"type": "proper.channels.Cable"}})
        with caplog.at_level(logging.WARNING, logger="proper"):
            app.cable.broadcast("room:1", "lost")
        assert "is lost" in caplog.text


class TestForwarding:
    def test_a_broadcast_from_another_process_arrives(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        code = (
            "from proper import App\n"
            f"app = App('proper', {_config(cable_app.config.CABLE_PORT)!r})\n"
            "assert not app.cable.serving\n"
            "app.cable.broadcast('room:1', {'from': 'a task'})\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True, timeout=60)
        assert client.recv_type("broadcast")["data"] == {"from": "a task"}
        client.close()

    def test_a_broadcast_answered_late_is_delivered_once(self, cable_app, monkeypatch):
        """A forwarded broadcast is answered once it is delivered. An answer
        later than `FORWARD_TIMEOUT` makes the sender try again, and the
        cable process must not deliver it a second time."""
        monkeypatch.setattr(base_module, "FORWARD_TIMEOUT", 0.3)
        reader = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        reader.subscribe(1)
        send_frame = cable_app.cable._send_frame
        delays = [0.6]  # the first delivery takes longer than the sender waits

        def slow_send_frame(stream_name, frame):
            if delays:
                time.sleep(delays.pop())
            send_frame(stream_name, frame)

        monkeypatch.setattr(cable_app.cable, "_send_frame", slow_send_frame)
        other = App("proper", _config(cable_app.config.CABLE_PORT))  # another process
        assert not other.cable.serving
        other.cable.broadcast("room:1", "once")  # sent twice: answered late
        frames = [reader.recv_type("broadcast")["data"]]
        # A second delivery of the copy would come before this one
        cable_app.cable.broadcast("room:1", "last")
        while frames[-1] != "last":
            msg = reader.recv_type("broadcast")
            assert msg is not None, frames
            frames.append(msg["data"])
        assert frames == ["once", "last"]
        reader.close()

    def test_batches_and_disconnects_are_forwarded(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        elsewhere = _new_app(cable_app.config.CABLE_PORT)  # not serving: forwards

        with elsewhere.cable.batch():
            elsewhere.cable.broadcast("room:1", "one")
            elsewhere.cable.broadcast("room:1", "two")
        assert client.recv_type("broadcast")["data"] == "one"
        assert client.recv_type("broadcast")["data"] == "two"

        elsewhere.cable.disconnect(user_id=7)
        assert client.recv_type("never") is None

    def test_the_serving_process_broadcasts_directly_even_in_a_batch(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        with cable_app.cable.batch():
            cable_app.cable.broadcast("room:1", "here")
            assert client.recv_type("broadcast")["data"] == "here"
        client.close()

    @pytest.mark.parametrize("path, token, status", [
        ("/cable", "forged", 403),
        ("/elsewhere", "forged", 404),
    ])
    def test_forged_or_misdirected_broadcasts_are_refused(self, cable_app, path, token, status):
        conn = http.client.HTTPConnection(
            "127.0.0.1", cable_app.config.CABLE_PORT + 1, timeout=TIMEOUT
        )
        conn.request("POST", path, body=token.encode())
        assert conn.getresponse().status == status
        conn.close()

    def test_a_forked_copy_forwards_instead_of_serving(self, cable_app):
        pid = cable_app.cable._owner_pid
        cable_app.cable._owner_pid = pid + 1  # as a fork sees it
        try:
            assert not cable_app.cable.serving
            assert cable_app.cable._forwarding
        finally:
            cable_app.cable._owner_pid = pid


BIG = "x" * 200_000


class TestStalledClients:
    """A client that stops reading is closed when it falls
    `CABLE_MAX_PENDING_BYTES` behind, and `cable.js` reconnects; one that
    reads slowly is not."""

    def test_a_client_too_far_behind_is_closed(self, make_app):
        app = make_app(CABLE_MAX_PENDING_BYTES=300_000)
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        # ~10 MB, which the client doesn't read: more than the kernel's
        # buffers take, so the rest waits in the cable's queue
        for _ in range(50):
            app.cable.broadcast("room:1", BIG)
            if ("unsubscribed", 1) in EVENTS:
                break
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        reader.close()

    def test_a_client_too_far_behind_for_its_own_messages_is_closed(self, make_app):
        app = make_app(CABLE_MAX_PENDING_BYTES=300_000)
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.subscribe(1)
        (conn,) = app.cable._connections.values()
        for _ in range(50):  # sent to it alone, not broadcast
            conn.put(json.dumps({"type": "big", "data": BIG}))
            if ("unsubscribed", 1) in EVENTS:
                break
        assert _wait(lambda: ("unsubscribed", 1) in EVENTS)
        reader.close()

    def test_a_client_that_reads_slowly_stays(self, make_app):
        app = make_app()  # 4 MB: more than all that is sent
        reader = WsClient(app.config.CABLE_PORT, _cookie(app), rcvbuf=4096)
        reader.read_pause = 0.005
        reader.subscribe(1)
        for _ in range(9):
            app.cable.broadcast("room:1", BIG)
        for n in range(9):
            assert reader.recv_type("broadcast") is not None, f"closed after {n} frames"
        assert ("unsubscribed", 1) not in EVENTS
        reader.close()


class TestIdleClients:
    """The cable closes a connection that sends it nothing for
    `idle_timeout` seconds. `cable.js` answers the pings, so a page that
    only listens stays connected."""

    def _pong(self):
        source = (BLUEPRINTS / "addon_channels/assets/js/cable.js").read_text()
        return re.search(r"const WSE_PONG = '(.+)'", source).group(1)

    def test_a_client_that_answers_the_pings_stays(self, make_app):
        """Two clients that only listen, one of which answers the pings.
        The test lasts until the cable closes the silent one: by then both
        have been connected for more than `idle_timeout`, and the one that
        answers must still be open. Pings every second and an
        `idle_timeout` of 3: an answer can be about 2 seconds late (a busy
        machine) before the client is taken for idle."""
        app = make_app(cable={"idle_timeout": 3}, CABLE_PING_INTERVAL=1)
        pong = self._pong()
        listener = WsClient(app.config.CABLE_PORT, _cookie(app))
        listener.subscribe(1)
        silent = WsClient(app.config.CABLE_PORT, _cookie(app))
        silent.subscribe(2)
        closed = threading.Event()

        def until_closed():
            silent.recv_type("never")  # `None` once the cable closes it
            closed.set()

        threading.Thread(target=until_closed, daemon=True).start()
        pings = 0
        until = time.monotonic() + 3 + TIMEOUT
        while not closed.is_set():
            assert time.monotonic() < until, "the cable never closed the silent client"
            msg = listener.recv(pings=True)  # one at least every second
            assert msg is not None, "the server closed a client that answers"
            if msg.get("c") == "WSE" and msg.get("t") == "ping":
                pings += 1
                listener.send_text(pong)

        assert pings > 0
        assert _wait(lambda: ("unsubscribed", 2) in EVENTS)
        listener.send(
            {
                "command": "message",
                "channel": "RoomChannel",
                "params": {"room": 1},
                "action": "count",
                "data": {"n": 1},
            }
        )
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


class TestObserving:
    def test_health(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        assert _wait(lambda: cable_app.cable.health()["streams"] == 1)
        health = cable_app.cable.health()
        assert (health["serving"], health["connections"], health["users"]) == (True, 1, 1)
        assert health["server"] == {
            "connections": 1, "recovery_enabled": True, "recovery_topic_count": 0,
            "recovery_bytes": 0,
            "presence_enabled": True, "presence_topics": 0,
        }
        client.close()

    def test_metrics_on_the_loopback_port(self, cable_app):
        client = WsClient(cable_app.config.CABLE_PORT, _cookie(cable_app))
        client.subscribe(1)
        assert _wait(lambda: cable_app.cable.streams == {"room:1": 1})
        conn = http.client.HTTPConnection(
            "127.0.0.1", cable_app.config.CABLE_PORT + 1, timeout=TIMEOUT
        )
        conn.request("GET", "/metrics")
        response = conn.getresponse()
        text = response.read().decode()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("text/plain; version=0.0.4")
        assert "# TYPE proper_cable_connections gauge\nproper_cable_connections 1\n" in text
        assert "proper_cable_streams 1\n" in text
        conn.request("GET", "/other")
        assert conn.getresponse().status == 404
        conn.close()
        client.close()

    def test_the_cable_port_answers_only_websockets(self, cable_app):
        conn = http.client.HTTPConnection("127.0.0.1", cable_app.config.CABLE_PORT, timeout=TIMEOUT)
        conn.request("GET", "/cable")
        assert conn.getresponse().status == 404
        conn.close()
