"""The WSGI face of the app: what a sync server calls, and what it gets back."""
import io
from urllib.parse import urlparse

import pytest

from proper import Controller, current
from proper.router import Route


SEEN: dict = {}


class Echo(Controller):
    def index(self):
        SEEN["request"] = self.request
        return self.render(text="ok")


class Form(Controller):
    def create(self):
        SEEN["form"] = dict(self.request.form)
        return self.render(text="saved")


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


def make_environ(url="/", *, method="GET", headers=(), body=b"", client=("10.0.0.9", "5555")):
    """A WSGI environ the way a server would build it."""
    upa = urlparse(url)
    scheme = upa.scheme or "http"
    host, _, port = (upa.netloc or "example.com").partition(":")
    port = port or ("443" if scheme == "https" else "80")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": (upa.path or "/").encode("utf-8").decode("latin-1"),
        "QUERY_STRING": upa.query or "",
        "SERVER_NAME": host,
        "SERVER_PORT": port,
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": client[0],
        "REMOTE_PORT": client[1],
        "wsgi.url_scheme": scheme,
        "wsgi.input": io.BytesIO(body),
        "HTTP_HOST": f"{host}:{port}",
    }
    for name, value in headers:
        key = name.upper().replace("-", "_")
        if key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            environ[key] = value
        else:
            environ[f"HTTP_{key}"] = value
    return environ


def call(app, environ):
    """Call the app like a WSGI server and return `(status, headers, body_iterable)`."""
    sent = {}

    def start_response(status, headers):
        sent["status"], sent["headers"] = status, headers

    body = app(environ, start_response)
    return sent["status"], sent["headers"], body


def header(headers, name):
    return {k.lower(): v for k, v in headers}.get(name)


class TestHttp:
    def test_request_is_built_from_the_environ(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ(
            "https://api.example.com:8443/echo?x=1",
            headers=[("x-custom", "a"), ("accept", "text/html")],
        )

        status, headers, body = call(app, environ)

        request = SEEN["request"]
        assert request.method == "GET"
        assert request.path == "/echo"
        assert request.query["x"] == "1"
        assert request.scheme == "https"
        assert request.host == "api.example.com"
        assert request.port == 8443
        assert request.client == ("10.0.0.9", 5555)
        assert request.headers["x-custom"] == "a"
        assert request.headers["accept"] == "text/html"
        assert status == "200 OK"
        assert header(headers, "content-type") == "text/plain; charset=utf-8"
        assert list(body) == [b"ok"]

    def test_a_non_ascii_path_is_decoded(self, app):
        _route(app, "/café", Echo.index)
        call(app, make_environ("/café"))
        assert SEEN["request"].path == "/café"

    def test_the_body_is_read_and_parsed(self, app):
        _route(app, "/form", Form.create, method="POST")
        body = b"name=ada&age=36"
        environ = make_environ("/form", method="POST", body=body, headers=[
            ("content-type", "application/x-www-form-urlencoded"),
            ("content-length", str(len(body))),
        ])

        status, _, _ = call(app, environ)

        assert SEEN["form"] == {"name": "ada", "age": "36"}
        assert status == "200 OK"

    def test_an_oversized_body_is_refused_unread(self, app):
        _route(app, "/form", Form.create, method="POST")
        app.config.MAX_CONTENT_LENGTH = 4
        environ = make_environ("/form", method="POST", body=b"name=ada&age=36", headers=[
            ("content-type", "application/x-www-form-urlencoded"),
            ("content-length", "15"),
        ])

        status, _, _ = call(app, environ)

        assert status.startswith("413")
        assert environ["wsgi.input"].tell() == 0
        app.config.MAX_CONTENT_LENGTH = 0

    def test_an_empty_body_is_an_empty_list(self, app):
        _route(app, "/empty", Empty.index)
        status, _, body = call(app, make_environ("/empty"))
        assert status == "204 No Content"
        assert body == []

    def test_head_sends_headers_only(self, app):
        _route(app, "/page", Page.index)
        status, headers, body = call(app, make_environ("/page", method="HEAD"))
        assert status == "200 OK"
        assert header(headers, "content-length") == "11"
        assert body == []

    def test_files_are_streamed(self, app, tmp_path):
        path = tmp_path / "report.txt"
        path.write_text("x" * 100)
        SEEN["path"] = path
        _route(app, "/report", Files.show)

        status, headers, body = call(app, make_environ("/report"))

        assert status == "200 OK"
        assert header(headers, "content-length") == "100"
        assert b"".join(body) == b"x" * 100
        body.close()
        assert body.filelike.closed

    def test_not_found(self, app):
        status, _, _ = call(app, make_environ("/nowhere"))
        assert status == "404 Not Found"

    def test_missing_addresses_are_none(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo")
        del environ["SERVER_NAME"], environ["REMOTE_ADDR"]
        call(app, environ)
        assert SEEN["request"].server is None
        assert SEEN["request"].client is None

    def test_an_unknown_status_has_no_reason(self, app):
        from proper.core.app_wsgi import _reason

        assert _reason(299) == ""


@pytest.fixture(autouse=True)
def _reset_current():
    yield
    current.request = None
    current.response = None
