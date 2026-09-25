"""The RSGI face of the app: what the server calls, and what it gets back."""
import asyncio
import multiprocessing
import sys
import time

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


def fake_serve(**options):
    """Stands in for a server: the children run until they are stopped, the
    one in the foreground returns at once. Module-level so a spawned process
    can import it."""
    if multiprocessing.parent_process() is not None:
        time.sleep(60)


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
    @pytest.fixture(autouse=True)
    def _quiet_and_free_threaded(self, monkeypatch):
        """The tests run on any build; the command sees a free-threaded one
        with the GIL off unless a test says otherwise."""
        monkeypatch.setattr("proper.helpers.show_banner", lambda: None)
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: None)
        monkeypatch.setattr("proper.cli.app_cli._free_threaded", lambda: True)
        monkeypatch.setattr("proper.cli.app_cli._gil_enabled", lambda: False)

    def _capture_group(self, monkeypatch):
        calls = {}
        monkeypatch.setattr(
            "proper.cli.app_cli._serve_group",
            lambda web, cable, processes: calls.update(web=web, cable=cable, processes=processes),
        )
        return calls

    def test_it_serves_the_app_target_over_wsgi(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.PORT = 4321
        app.config.WORKERS = 3
        app.config.APP_TARGET = "myapp.main:app"

        get_run_cli(app)(None)

        web = calls["web"]
        assert web["target"] == "myapp.main:app"
        assert web["interface"] == "wsgi"
        assert web["address"] == "0.0.0.0"
        assert web["port"] == 4321
        assert web["workers"] == 3
        assert web["blocking_threads"] >= 1
        assert web["debug"] is False
        assert calls["cable"] is None
        assert calls["processes"] == 1

    def test_the_target_defaults_to_the_creating_module(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.APP_TARGET = ""
        app.config.RELOAD = False

        get_run_cli(app)(None, host="127.0.0.1", port=9000, workers=2)

        assert calls["web"]["target"] == f"{app.import_name}:app"
        assert calls["web"]["address"] == "127.0.0.1"
        assert calls["web"]["port"] == 9000
        assert calls["web"]["workers"] == 2

    def test_granian_gets_the_options(self, monkeypatch):
        import granian

        from proper.cli.app_cli import _serve

        calls = {}

        class FakeGranian:
            def __init__(self, **kwargs):
                calls.update(kwargs)

            def serve(self):
                calls["served"] = True

        monkeypatch.setattr(granian, "Granian", FakeGranian)
        _serve(
            target="myapp:app", interface="wsgi", address="0.0.0.0", port=2300,
            workers=2, blocking_threads=5, debug=False,
        )
        assert calls["target"] == "myapp:app"
        assert calls["interface"] == "wsgi"
        assert calls["blocking_threads"] == 5
        assert calls["websockets"] is False
        assert calls["served"] is True

        _serve(
            target="myapp:app", interface="rsgi", address="0.0.0.0", port=2301,
            workers=1, blocking_threads=5, debug=True,
        )
        assert calls["interface"] == "rsgi"
        assert calls["websockets"] is True
        # Granian's blocking threads only mean something for WSGI.
        assert calls["blocking_threads"] is None
        assert calls["log_access"] is True

    def test_rsgi_is_a_choice(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.INTERFACE = "RSGI"
        app.config.CABLE_PORT = 2301

        get_run_cli(app)(None)

        assert calls["web"]["interface"] == "rsgi"
        assert calls["cable"] is None  # RSGI serves the WebSockets itself

    def test_an_unknown_interface_is_refused(self, app):
        from proper.cli.app_cli import get_run_cli

        app.config.INTERFACE = "asgi"
        with pytest.raises(ValueError, match="INTERFACE"):
            get_run_cli(app)(None)

    def test_the_thread_budget_is_split_between_workers(self):
        from proper.cli.app_cli import _blocking_threads

        assert _blocking_threads(20, 4) == 5
        assert _blocking_threads(20, 3) == 7  # rounded up
        assert _blocking_threads(2, 8) == 1
        assert _blocking_threads(0, 4) == 1

    def test_reloading_restarts_the_whole_group_from_outside(self, app, monkeypatch):
        import watchfiles

        from proper.cli import app_cli

        calls = {}
        monkeypatch.setattr(
            watchfiles, "run_process", lambda *paths, **kw: calls.update(paths=paths, **kw)
        )
        app.config.RELOAD = True
        app.config.CABLE_PORT = 2301
        app.config.PROCESSES = 2

        app_cli.get_run_cli(app)(None, port=2300)

        assert calls["paths"] == (str(app.root_path),)
        assert calls["target"] is app_cli._serve_group
        assert calls["kwargs"]["web"]["port"] == 2300
        assert calls["kwargs"]["cable"]["port"] == 2301
        assert calls["kwargs"]["processes"] == 2
        assert calls["callback"] is app_cli._log_changes

    def test_the_restart_says_which_files_changed(self, capsys):
        from watchfiles import Change

        from proper.cli.app_cli import _log_changes

        _log_changes({(Change.modified, "b.py"), (Change.added, "a.py")})

        assert "restarting the server: a.py, b.py" in capsys.readouterr().out

    def test_a_cable_port_adds_a_websocket_process(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.CABLE_PORT = 2301
        app.config.WORKERS = 4

        get_run_cli(app)(None, port=2300)

        cable = calls["cable"]
        assert cable["interface"] == "rsgi"
        assert cable["port"] == 2301
        assert cable["workers"] == 1
        assert cable["target"] == calls["web"]["target"]
        assert calls["web"]["workers"] == 4

    def test_processes_come_from_the_config(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.PROCESSES = 3
        get_run_cli(app)(None)
        assert calls["processes"] == 3

        app.config.PROCESSES = 0  # nonsense is one
        get_run_cli(app)(None)
        assert calls["processes"] == 1

    def test_the_group_goes_down_with_the_web_server(self):
        from proper.cli.app_cli import _serve_group

        children = _serve_group(
            {"interface": "wsgi"}, {"interface": "rsgi"}, processes=3, serve=fake_serve
        )

        assert [child.name for child in children] == ["proper-cable", "proper-web-2", "proper-web-3"]
        assert all(not child.is_alive() for child in children)
        assert all(child.exitcode is not None for child in children)

    def test_the_gil_is_refused(self, app, monkeypatch, capsys):
        from proper.cli.app_cli import get_run_cli

        monkeypatch.setattr("proper.cli.app_cli._free_threaded", lambda: False)
        monkeypatch.setattr("proper.cli.app_cli._gil_enabled", lambda: True)

        with pytest.raises(SystemExit):
            get_run_cli(app)(None)

        err = capsys.readouterr().err
        assert "uv python install 3.14t" in err
        assert "ALLOW_GIL" in err

    def test_an_extension_that_turned_the_gil_on_is_refused(self, app, monkeypatch, capsys):
        from proper.cli.app_cli import get_run_cli

        monkeypatch.setattr("proper.cli.app_cli._gil_enabled", lambda: True)

        with pytest.raises(SystemExit):
            get_run_cli(app)(None)

        assert "RuntimeWarning" in capsys.readouterr().err

    def test_allow_gil_serves_with_a_warning(self, app, monkeypatch, capsys):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        monkeypatch.setattr("proper.cli.app_cli._free_threaded", lambda: False)
        monkeypatch.setattr("proper.cli.app_cli._gil_enabled", lambda: True)
        app.config.ALLOW_GIL = True

        get_run_cli(app)(None)

        assert calls["processes"] == 1
        assert "Serving with the GIL" in capsys.readouterr().out



def test_the_build_checks_follow_the_interpreter():
    import sysconfig

    from proper.cli.app_cli import _free_threaded, _gil_enabled

    assert _free_threaded() is bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    assert _gil_enabled() is getattr(sys, "_is_gil_enabled", lambda: True)()


@pytest.fixture(autouse=True)
def _reset_current():
    yield
    current.request = None
    current.response = None
