"""The RSGI face of the app: what the server calls, and what it gets back."""
import asyncio

import pytest

from proper import Channel, Controller, current
from proper.app import _split_address
from proper.router import Route
from proper.test_client import (
    HttpProtocolStub,
    WebSocketTestSession,
    WsProtocolStub,
    make_test_scope,
    make_test_ws_scope,
)


class TestSplitAddress:
    def test_host_and_port(self):
        assert _split_address("127.0.0.1:8000") == ("127.0.0.1", 8000)

    def test_ipv6(self):
        assert _split_address("[::1]:8000") == ("::1", 8000)

    def test_no_port(self):
        assert _split_address("example.com") == ("example.com", None)
        assert _split_address("[::1]") == ("::1", None)

    def test_empty(self):
        assert _split_address("") is None
        assert _split_address(None) is None

SEEN: dict = {}


class Echo(Controller):
    def index(self):
        SEEN["request"] = self.request
        return self.render(text="ok")


class Form(Controller):
    def create(self):
        SEEN["form"] = dict(self.request.form)
        return self.render(text="saved")


class Never(Controller):
    def create(self):
        return self.render(text="never")


class Empty(Controller):
    def index(self):
        self.response.status = 204
        return ""


class Page(Controller):
    def index(self):
        return self.render(text="hello world")


class Files(Controller):
    def show(self):
        self.response.send_file(SEEN["path"])


def _route(app, path, action, method="GET"):
    app.router.add_route(Route(method=method, path=path, to=action))


class TestHttp:
    async def test_request_is_built_from_the_scope(self, app):
        _route(app, "/echo", Echo.index)
        scope = make_test_scope(
            "https://api.example.com:8443/echo?x=1",
            headers=[("x-dup", "a"), ("x-dup", "b")],
            client="10.0.0.9:5555",
        )
        protocol = HttpProtocolStub()

        await app.__rsgi__(scope, protocol)

        request = SEEN["request"]
        assert request.method == "GET"
        assert request.path == "/echo"
        assert request.query["x"] == "1"
        assert request.scheme == "https"
        assert request.host == "api.example.com"
        assert request.port == 8443
        assert request.client == ("10.0.0.9", 5555)
        assert request.headers.getall("x-dup") == ["a", "b"]
        assert protocol.status == 200
        assert protocol.body == b"ok"
        assert ("content-type", "text/plain; charset=utf-8") in [
            (k.lower(), v) for k, v in protocol.headers
        ]

    async def test_the_body_is_read_and_parsed(self, app):
        _route(app, "/form", Form.create, method="POST")
        body = b"name=ada&age=36"
        scope = make_test_scope("/form", method="POST", headers=[
            ("content-type", "application/x-www-form-urlencoded"),
            ("content-length", str(len(body))),
        ])
        protocol = HttpProtocolStub(body)

        await app.__rsgi__(scope, protocol)

        assert SEEN["form"] == {"name": "ada", "age": "36"}
        assert protocol.status == 200

    async def test_an_oversized_body_is_refused(self, app):

        _route(app, "/form", Form.create, method="POST")
        app.config.MAX_CONTENT_LENGTH = 4
        scope = make_test_scope("/form", method="POST", headers=[
            ("content-type", "application/x-www-form-urlencoded"),
            ("content-length", "15"),
        ])
        protocol = HttpProtocolStub(b"name=ada&age=36")

        await app.__rsgi__(scope, protocol)

        assert protocol.status == 413
        app.config.MAX_CONTENT_LENGTH = 0

    async def test_an_empty_body_is_sent_as_empty(self, app):

        _route(app, "/empty", Empty.index)
        protocol = HttpProtocolStub()

        await app.__rsgi__(make_test_scope("/empty"), protocol)

        assert protocol.status == 204
        assert protocol.body == b""
        assert not protocol.streamed

    async def test_head_sends_headers_only(self, app):

        _route(app, "/page", Page.index)
        protocol = HttpProtocolStub()

        await app.__rsgi__(make_test_scope("/page", method="HEAD"), protocol)

        assert protocol.status == 200
        assert protocol.body == b""
        assert ("content-length", "11") in [(k.lower(), v) for k, v in protocol.headers]

    async def test_files_are_handed_to_the_server(self, app, tmp_path):
        path = tmp_path / "report.txt"
        path.write_text("x" * 100)
        SEEN["path"] = path

        _route(app, "/report", Files.show)
        protocol = HttpProtocolStub()

        await app.__rsgi__(make_test_scope("/report"), protocol)

        assert protocol.status == 200
        assert protocol.file == str(path)
        assert protocol.body == b""
        assert not protocol.streamed
        # The wrapper opened for other consumers is closed, not leaked.
        assert current.response.body.filelike.closed

    async def test_not_found(self, app):
        protocol = HttpProtocolStub()
        await app.__rsgi__(make_test_scope("/nowhere"), protocol)
        assert protocol.status == 404


class TestWebSocket:
    async def test_the_session_drives_a_channel_end_to_end(self, app):
        class EchoChannel(Channel):
            def subscribed(self):
                self.stream_from("echo")

            def speak(self, data):
                self.broadcast("echo", {"said": data["text"]})

        app.router.channels["EchoChannel"] = EchoChannel
        session = WebSocketTestSession(app, "/cable")

        task = await session.connect()
        assert await session.receive_raw() == {"type": "accept"}

        confirm = await session.subscribe("EchoChannel")
        assert confirm["type"] == "confirm_subscription"

        await session.send_action("EchoChannel", "speak", {"text": "hi"})
        msg = await session.receive()
        assert msg["data"] == {"said": "hi"}

        await session.unsubscribe("EchoChannel")
        await session.close()
        await task

    async def test_a_wrong_path_is_closed(self, app):
        session = WebSocketTestSession(app, "/elsewhere")
        task = await session.connect()
        assert await session.receive_raw() == {"type": "close", "code": 404}
        await task

    async def test_a_dropped_connection_ends_the_handler(self, app):
        class Dropped(WsProtocolStub):
            async def receive(self):
                raise ConnectionResetError("gone")

        protocol = Dropped()
        await asyncio.wait_for(
            app._handle_websocket(make_test_ws_scope(), protocol), timeout=1
        )
        assert await protocol.client_recv() == {"type": "accept"}

    async def test_binary_and_empty_frames_are_ignored(self, app):
        protocol = WsProtocolStub()
        protocol.client_send_bytes(b"\x00\x01")
        protocol.client_send_text("")
        protocol.client_disconnect()

        await asyncio.wait_for(
            app._handle_websocket(make_test_ws_scope(), protocol), timeout=1
        )

        assert await protocol.client_recv() == {"type": "accept"}
        assert protocol.from_app.empty()


class TestLifecycle:
    def test_the_server_hooks_run_startup_and_shutdown(self, app):
        loop = asyncio.new_event_loop()
        try:
            app.__rsgi_init__(loop)
            assert app._executor is not None
            assert app._executor_users == 1

            app.__rsgi_del__(loop)
            assert app._executor is None
        finally:
            loop.close()


class TestRunCommand:
    def test_it_starts_granian_with_the_app_target(self, app, monkeypatch):
        import granian

        from proper.cli.app_cli import get_run_cli

        calls = {}

        class FakeGranian:
            def __init__(self, **kwargs):
                calls.update(kwargs)

            def serve(self):
                calls["served"] = True

        monkeypatch.setattr(granian, "Granian", FakeGranian)
        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        app.config.PORT = 4321
        app.config.WORKERS = 3
        app.config.APP_TARGET = "myapp.main:app"

        get_run_cli(app)(None)

        assert calls["target"] == "myapp.main:app"
        assert calls["interface"] == "wsgi"
        assert calls["websockets"] is False
        assert calls["port"] == 4321
        assert calls["workers"] == 3
        assert calls["blocking_threads"] >= 1
        assert calls["address"] == "0.0.0.0"
        assert calls["reload"] is False
        assert calls["served"] is True

    def test_rsgi_is_a_choice(self, app, monkeypatch):
        import granian

        from proper.cli.app_cli import get_run_cli

        calls = {}

        class FakeGranian:
            def __init__(self, **kwargs):
                calls.update(kwargs)

            def serve(self):
                pass

        monkeypatch.setattr(granian, "Granian", FakeGranian)
        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        app.config.INTERFACE = "RSGI"

        get_run_cli(app)(None)

        assert calls["interface"] == "rsgi"
        assert calls["websockets"] is True
        # Granian's blocking threads only mean something for WSGI.
        assert calls["blocking_threads"] is None

    def test_an_unknown_interface_is_refused(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        app.config.INTERFACE = "asgi"

        with pytest.raises(ValueError, match="INTERFACE"):
            get_run_cli(app)(None)

    def test_the_thread_budget_is_split_between_free_threaded_workers(
        self, monkeypatch
    ):
        from proper.cli import app_cli

        monkeypatch.setattr(app_cli, "_free_threaded", lambda: True)
        assert app_cli._blocking_threads(20, 4) == 5
        assert app_cli._blocking_threads(20, 3) == 7  # rounded up
        assert app_cli._blocking_threads(2, 8) == 1

    def test_process_workers_each_get_the_whole_budget(self, monkeypatch):
        from proper.cli import app_cli

        monkeypatch.setattr(app_cli, "_free_threaded", lambda: False)
        assert app_cli._blocking_threads(20, 4) == 20
        assert app_cli._blocking_threads(0, 4) == 1

    def test_the_target_defaults_to_the_creating_module(self, app, monkeypatch):
        import granian

        from proper.cli.app_cli import get_run_cli

        calls = {}

        class FakeGranian:
            def __init__(self, **kwargs):
                calls.update(kwargs)

            def serve(self):
                pass

        monkeypatch.setattr(granian, "Granian", FakeGranian)
        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        monkeypatch.setattr("proper.cli.app_cli._free_threaded", lambda: False)
        app.config.APP_TARGET = ""
        app.config.DEBUG = True
        app.config.RELOAD = None

        get_run_cli(app)(None, host="127.0.0.1", port=9000, workers=2)

        assert calls["target"] == f"{app.import_name}:app"
        assert calls["address"] == "127.0.0.1"
        assert calls["port"] == 9000
        assert calls["workers"] == 2
        assert calls["reload"] is True

    def test_free_threaded_python_restarts_the_server_from_outside(
        self, app, monkeypatch
    ):
        import watchfiles

        from proper.cli import app_cli

        calls = {}

        def run_process(*paths, **kwargs):
            calls["paths"] = paths
            calls.update(kwargs)

        monkeypatch.setattr(watchfiles, "run_process", run_process)
        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        monkeypatch.setattr(app_cli, "_free_threaded", lambda: True)
        app.config.RELOAD = True
        app.config.APP_TARGET = "myapp.main:app"

        app_cli.get_run_cli(app)(None, port=9000)

        assert calls["paths"] == (str(app.root_path),)
        assert calls["target"] is app_cli._serve
        assert calls["kwargs"]["target"] == "myapp.main:app"
        assert calls["kwargs"]["port"] == 9000
        # The child must not try Granian's own reloader again.
        assert calls["kwargs"]["reload"] is False
        assert calls["callback"] is app_cli._log_changes

    def test_the_restart_says_which_files_changed(self, capsys):
        from watchfiles import Change

        from proper.cli.app_cli import _log_changes

        _log_changes({(Change.modified, "b.py"), (Change.added, "a.py")})

        assert "restarting the server: a.py, b.py" in capsys.readouterr().out

    def test_free_threaded_follows_the_build(self):
        import sysconfig

        from proper.cli.app_cli import _free_threaded

        assert _free_threaded() is bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


@pytest.fixture(autouse=True)
def _reset_current():
    yield
    current.request = None
    current.response = None
