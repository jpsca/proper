"""`proper run`: what it starts, and how."""
import http.client
import multiprocessing
import os
import signal
import socket
import sys
import time
from types import SimpleNamespace

import pytest

from proper import App
from proper.app import _default_max_threads


def fake_serve(**options):
    """Stands in for a server: the children run until they are stopped, the
    one in the foreground returns at once. Module-level so a spawned process
    can import it."""
    if multiprocessing.parent_process() is not None:
        time.sleep(60)


class _OwnCable:
    """A cable that serves its own WebSockets, recording what happens."""

    serves_websockets = True

    def __init__(self):
        self.events = []

    def start_server(self):
        self.events.append("start")

    def stop_server(self):
        self.events.append("stop")


OWNER = SimpleNamespace(cable=_OwnCable())
# A target with `_bearings`, as every Proper app has
RAW_OWNER = SimpleNamespace(_bearings=lambda head, input, listener: (200, [], b""))


def hello_app(environ, start_response):
    """A WSGI app a spawned process can import."""
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"hello"]


class TestMaxThreads:
    def test_the_default_matches_pythons(self):
        app = App("proper", {"SECRET_KEYS": ["*" * 50]})
        assert app.max_threads == _default_max_threads()

    def test_the_config_sets_it(self):
        app = App("proper", {"SECRET_KEYS": ["*" * 50], "MAX_THREADS": 3})
        assert app.max_threads == 3


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
            lambda web, processes, start_cable=False: calls.update(
                web=web, processes=processes, start_cable=start_cable
            ),
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
        assert web["address"] == "0.0.0.0"
        assert web["port"] == 4321
        assert web["workers"] == 3
        assert web["threads"] == app.max_threads
        assert web["debug"] is False
        assert calls["processes"] == 1
        assert calls["start_cable"] is False

    def _capture_welcome(self, monkeypatch):
        shown = []
        monkeypatch.setattr("proper.helpers.show_banner", lambda: shown.append("banner"))
        monkeypatch.setattr("proper.helpers.show_welcome", lambda host: shown.append(host))
        return shown

    def test_the_welcome_is_shown_in_debug(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        self._capture_group(monkeypatch)
        shown = self._capture_welcome(monkeypatch)
        app.config.DEBUG = True
        app.config.RELOAD = False
        app.config.HOST = "localhost:2300"

        get_run_cli(app)(None)

        assert shown == ["banner", "localhost:2300"]

    def test_the_welcome_is_not_shown_outside_debug(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        self._capture_group(monkeypatch)
        shown = self._capture_welcome(monkeypatch)
        app.config.DEBUG = False

        get_run_cli(app)(None)

        assert shown == []

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

    def test_bearings_gets_the_options(self, monkeypatch, capsys):
        import bearings

        from proper.cli.app_cli import _serve

        calls = {}

        def fake_serve(app, **options):
            calls.update(app=app, **options)
            options["started"](SimpleNamespace(port=2300))

        monkeypatch.setattr(bearings, "serve", fake_serve)
        _serve(
            target=f"{__name__}:OWNER", address="0.0.0.0", port=2300,
            workers=2, threads=5, debug=False,
        )
        assert calls["app"] is OWNER
        assert calls["raw"] is False
        assert calls["host"] == "0.0.0.0"
        assert calls["port"] == 2300
        assert calls["loops"] == 2
        assert calls["workers"] == 5
        assert calls["access_log"] is None
        assert "[INFO] Listening on 0.0.0.0:2300 (2 workers, 5 threads" in (
            capsys.readouterr().out
        )

        _serve(
            target=f"{__name__}:OWNER", address="0.0.0.0", port=2300,
            workers=1, threads=5, debug=True,
        )
        assert calls["access_log"] == "combined"

    def test_a_proper_app_is_served_raw(self, monkeypatch):
        import bearings

        from proper.cli.app_cli import _serve

        calls = {}
        monkeypatch.setattr(bearings, "serve", lambda app, **options: calls.update(
            app=app, **options
        ))
        _serve(
            target=f"{__name__}:RAW_OWNER", address="0.0.0.0", port=2300,
            workers=1, threads=1, debug=False,
        )
        assert calls["app"] == RAW_OWNER._bearings
        assert calls["raw"] is True

    def test_it_serves_until_sigterm(self):
        from proper.cli.app_cli import _serve

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        web = {
            "target": f"{__name__}:hello_app", "address": "127.0.0.1", "port": port,
            "workers": 1, "threads": 2, "debug": False,
        }
        child = multiprocessing.get_context("spawn").Process(target=_serve, kwargs=web)
        child.start()
        try:
            body = None
            for _ in range(100):  # until it listens
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("GET", "/")
                    body = conn.getresponse().read()
                    conn.close()
                    break
                except OSError:
                    time.sleep(0.05)
            assert body == b"hello"
            os.kill(child.pid, signal.SIGTERM)
            child.join(10)
            assert child.exitcode == 0
        finally:
            if child.is_alive():
                child.kill()

    def test_reloading_restarts_the_whole_group_from_outside(self, app, monkeypatch):
        import watchfiles

        from proper.cli import app_cli

        calls = {}
        monkeypatch.setattr(
            watchfiles, "run_process", lambda *paths, **kw: calls.update(paths=paths, **kw)
        )
        app.config.RELOAD = True
        app.config.PROCESSES = 2

        app_cli.get_run_cli(app)(None, port=2300)

        assert calls["paths"] == (str(app.root_path),)
        assert calls["target"] is app_cli._serve_group
        assert calls["kwargs"]["web"]["port"] == 2300
        assert calls["kwargs"]["processes"] == 2
        assert calls["callback"] is app_cli._log_changes

    def test_the_restart_says_which_files_changed(self, capsys):
        from watchfiles import Change

        from proper.cli.app_cli import _log_changes

        _log_changes({(Change.modified, "b.py"), (Change.added, "a.py")})

        assert "restarting the server: a.py, b.py" in capsys.readouterr().out

    def test_a_cable_that_serves_itself_starts_with_the_group(self, app, monkeypatch):
        from proper.cli.app_cli import get_run_cli

        calls = self._capture_group(monkeypatch)
        app.config.CABLE_PORT = 2301
        app.cable = _OwnCable()

        get_run_cli(app)(None, port=2300)

        assert calls["start_cable"] is True

    def test_the_group_runs_the_cable_around_the_web_server(self):
        from proper.cli.app_cli import _serve_group

        OWNER.cable.events.clear()
        _serve_group(
            {"target": f"{__name__}:OWNER"},
            start_cable=True,
            serve=lambda **web: OWNER.cable.events.append("serve"),
        )
        assert OWNER.cable.events == ["start", "serve", "stop"]

    def test_load_app_defaults_to_the_app_attribute(self, monkeypatch):
        from proper.cli.app_cli import _load_app

        monkeypatch.setattr(sys.modules[__name__], "app", OWNER, raising=False)
        assert _load_app(__name__) is OWNER
        assert _load_app(f"{__name__}:OWNER") is OWNER

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

        children = _serve_group({}, processes=3, serve=fake_serve)

        assert [child.name for child in children] == ["proper-web-2", "proper-web-3"]
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
