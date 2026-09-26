"""Broadcasts made in a process without WebSockets reach the cable process."""
import logging
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from proper import App, Channel
from proper.channels import CABLE_SALT, Cable
from proper.test_client import HttpProtocolStub, make_test_scope


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


def _channel(app, sent):
    return Channel(app, {}, _send=sent.append)


class TestForwarding:
    def test_the_cable_tool_forwards_when_there_is_a_cable_port(self):
        app = make_app(CABLE_PORT=2301, CABLE_PATH="/ws")
        assert app.cable._forward_url == "http://127.0.0.1:2301/ws"

    def test_no_cable_port_no_forwarding(self):
        app = make_app()
        assert app.cable._forward_url is None

    def test_a_broadcast_is_posted_signed(self, cable_server):
        app = make_app()
        cable = Cable()
        cable.forward_to(cable_server, sign=partial(app.dumps, salt=CABLE_SALT))
        sent = []
        cable.subscribe("chat", _channel(app, sent))

        cable.broadcast("chat", {"text": "hi"})

        assert sent == []  # not delivered here: this process has no sockets
        [(path, token)] = Recorder.received
        assert path == "/cable"
        assert app.loads(token, salt=CABLE_SALT) == {"stream": "chat", "data": {"text": "hi"}}

    async def test_once_started_the_cable_delivers_locally(self, cable_server):
        app = make_app()
        cable = Cable()
        cable.forward_to(cable_server, sign=partial(app.dumps, salt=CABLE_SALT))
        sent = []
        cable.subscribe("chat", _channel(app, sent))
        await cable.start()

        cable.broadcast("chat", {"text": "hi"})

        assert [msg["data"] for msg in sent] == [{"text": "hi"}]
        assert Recorder.received == []

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
    async def _post(self, app, body: bytes):
        protocol = HttpProtocolStub(body)
        scope = make_test_scope(
            app.config.CABLE_PATH, method="POST",
            headers=[("content-length", str(len(body)))],
        )
        await app.__rsgi__(scope, protocol)
        return protocol

    async def test_a_signed_broadcast_is_delivered(self):
        app = make_app()
        sent = []
        app.cable.subscribe("chat", _channel(app, sent))
        token = app.dumps({"stream": "chat", "data": {"text": "hi"}}, salt=CABLE_SALT)

        protocol = await self._post(app, token.encode())

        assert protocol.status == 204
        assert [msg["data"] for msg in sent] == [{"text": "hi"}]

    async def test_a_bad_signature_is_refused(self, caplog):
        app = make_app()
        sent = []
        app.cable.subscribe("chat", _channel(app, sent))
        forged = app.dumps({"stream": "chat", "data": {}}, salt="other")

        with caplog.at_level(logging.WARNING, logger="proper"):
            protocol = await self._post(app, forged.encode())

        assert protocol.status == 403
        assert sent == []
        assert "bad signature" in caplog.text

    async def test_a_signed_token_without_a_stream_is_refused(self):
        app = make_app()
        token = app.dumps(["not", "a", "broadcast"], salt=CABLE_SALT)
        protocol = await self._post(app, token.encode())
        assert protocol.status == 403

    async def test_a_get_on_the_cable_path_is_still_a_page(self):
        app = make_app()
        protocol = HttpProtocolStub()
        await app.__rsgi__(make_test_scope(app.config.CABLE_PATH), protocol)
        assert protocol.status == 404  # no such route, as before
