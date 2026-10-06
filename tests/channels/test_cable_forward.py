"""Broadcasts made in a process without WebSockets reach the one that
serves them: what `Cable` sends, and what it does with what it receives."""
import logging
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from proper import App
from proper.channels import CABLE_SALT, Cable


def make_app(**config):
    return App("proper", {"SECRET_KEYS": ["*" * 50], **config})


class Recorder(BaseHTTPRequestHandler):
    """Stands in for the cable process: records what is posted."""

    received: list = []
    status = 204

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        Recorder.received.append((self.path, self.rfile.read(length).decode()))
        self.send_response(Recorder.status)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture()
def cable_server():
    Recorder.received = []
    Recorder.status = 204
    server = HTTPServer(("127.0.0.1", 0), Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/cable"
    server.shutdown()
    server.server_close()


class TestForwarding:
    def test_the_cable_forwards_to_the_port_after_the_cable_port(self):
        app = make_app(
            CABLE={"type": "proper.channels.wse.WseCable"}, CABLE_PORT=2301, CABLE_PATH="/ws"
        )
        assert app.cable._forward_url == "http://127.0.0.1:2302/ws"

    def test_no_cable_port_no_forwarding(self):
        app = make_app()
        assert app.cable._forward_url is None

    def test_a_broadcast_is_posted_signed(self, cable_server):
        app = make_app()
        cable = Cable()
        cable.forward_to(cable_server, sign=partial(app.dumps, salt=CABLE_SALT))

        cable.broadcast("chat", {"text": "hi"})

        [(path, token)] = Recorder.received
        assert path == "/cable"
        assert app.loads(token, salt=CABLE_SALT) == {"stream": "chat", "data": {"text": "hi"}}

    def test_a_batch_is_one_request(self, cable_server):
        app = make_app()
        cable = Cable()
        cable.forward_to(cable_server, sign=partial(app.dumps, salt=CABLE_SALT))

        with cable.batch():
            cable.broadcast("a", 1)
            with cable.batch():  # nested: the outer one sends
                cable.broadcast("b", 2)
            cable.disconnect(user_id=7)  # not batched

        [(_, disconnect), (_, batch)] = Recorder.received
        assert app.loads(disconnect, salt=CABLE_SALT) == {"disconnect": {"user_id": 7}}
        assert app.loads(batch, salt=CABLE_SALT) == {
            "batch": [{"stream": "a", "data": 1}, {"stream": "b", "data": 2}]
        }

    def test_without_forwarding_a_broadcast_reaches_no_one(self, caplog):
        cable = make_app().cable

        with caplog.at_level(logging.DEBUG, logger="proper"):
            cable.broadcast("chat", {"text": "hi"})
            cable.disconnect(user_id=7)

        assert "the broadcast to chat reaches no one" in caplog.text
        assert cable.streams == {}

    def test_a_cable_that_is_down_is_a_warning(self, caplog):
        app = make_app()
        cable = Cable()
        cable.forward_to("http://127.0.0.1:1/cable", sign=partial(app.dumps, salt=CABLE_SALT))

        with caplog.at_level(logging.WARNING, logger="proper"):
            cable.broadcast("chat", {"text": "hi"})

        assert "could not reach the cable process" in caplog.text

    def test_a_refusal_is_a_warning(self, cable_server, caplog):
        Recorder.status = 403
        app = make_app()
        cable = Cable()
        cable.forward_to(cable_server, sign=partial(app.dumps, salt=CABLE_SALT))

        with caplog.at_level(logging.WARNING, logger="proper"):
            cable.broadcast("chat", {"text": "hi"})

        assert "refused a broadcast: HTTP 403" in caplog.text


class TestReceiving:
    def test_a_signed_broadcast_is_delivered(self, caplog):
        app = make_app()
        token = app.dumps(
            {"stream": "chat", "data": {}, "batch": [{"stream": "room", "data": {}}],
             "disconnect": {"user_id": 7}},
            salt=CABLE_SALT,
        )

        with caplog.at_level(logging.DEBUG, logger="proper"):
            assert app.cable.receive_forwarded(token, app.loads) is True

        assert "the broadcast to chat reaches no one" in caplog.text
        assert "the broadcast to room reaches no one" in caplog.text

    def test_a_bad_signature_is_refused(self, caplog):
        app = make_app()
        forged = app.dumps({"stream": "chat", "data": {}}, salt="other")

        with caplog.at_level(logging.WARNING, logger="proper"):
            assert app.cable.receive_forwarded(forged, app.loads) is False

        assert "bad signature" in caplog.text

    def test_a_signed_token_without_a_stream_is_refused(self):
        app = make_app()
        token = app.dumps(["not", "a", "broadcast"], salt=CABLE_SALT)
        assert app.cable.receive_forwarded(token, app.loads) is False
