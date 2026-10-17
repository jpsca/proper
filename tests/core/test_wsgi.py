"""The WSGI face of the app: what a sync server calls, and what it gets back."""
import contextvars
import io
import threading
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
        # As Bearings: `wsgi.input` returns `b""` at the end of the body.
        "wsgi.input_terminated": True,
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


def call_on_a_small_stack(app, environ):
    """`call()` on a thread with a stack of at most 4 MB.

    How deep `json` nests before a `RecursionError` depends on the stack of
    the thread, and the main thread's is `ulimit -s`, which changes from
    machine to machine. A thread gets the size it asks for, or a stack of a
    finished thread that glibc kept, of up to 4 times that size: 1 MB asked,
    at most 4 MB used (about 29 000 nested arrays).
    """
    stack_size = 1024 * 1024
    result = {}
    context = contextvars.copy_context()
    previous = threading.stack_size(stack_size)
    try:
        thread = threading.Thread(
            target=lambda: result.update(sent=context.run(call, app, environ))
        )
        thread.start()
    finally:
        threading.stack_size(previous)
    thread.join()
    return result["sent"]


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
        assert request.server_software == ""
        assert request.headers["x-custom"] == "a"
        assert request.headers["accept"] == "text/html"
        assert status == "200 OK"
        assert header(headers, "content-type") == "text/plain; charset=utf-8"
        assert list(body) == [b"ok"]

    def test_the_name_of_the_server_is_taken_from_the_environ(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo")
        environ["SERVER_SOFTWARE"] = "gunicorn/23.0.0"

        call(app, environ)

        assert SEEN["request"].server_software == "gunicorn/23.0.0"

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

    def test_an_urlencoded_body_with_too_many_fields_is_refused(self, app):
        _route(app, "/form", Form.create, method="POST")
        app.config.MAX_FORM_FIELDS = 2
        body = b"a=1&b=2&c=3"
        environ = make_environ("/form", method="POST", body=body, headers=[
            ("content-type", "application/x-www-form-urlencoded"),
            ("content-length", str(len(body))),
        ])

        status, _, _ = call(app, environ)

        assert status.startswith("400")
        app.config.MAX_FORM_FIELDS = 100

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

    def test_a_chunked_body_is_read_and_parsed(self, app):
        _route(app, "/form", Form.create, method="POST")
        environ = make_environ(
            "/form",
            method="POST",
            body=b"name=ada&age=36",
            headers=[
                ("content-type", "application/x-www-form-urlencoded"),
                ("transfer-encoding", "chunked"),
            ],
        )

        status, _, _ = call(app, environ)

        assert SEEN["form"] == {"name": "ada", "age": "36"}
        assert status == "200 OK"

    def test_an_oversized_chunked_body_is_refused(self, app):
        _route(app, "/form", Form.create, method="POST")
        app.config.MAX_CONTENT_LENGTH = 4
        environ = make_environ(
            "/form",
            method="POST",
            body=b"name=ada&age=36",
            headers=[
                ("content-type", "application/x-www-form-urlencoded"),
                ("transfer-encoding", "chunked"),
            ],
        )

        status, _, _ = call(app, environ)

        assert status.startswith("413")
        assert environ["wsgi.input"].tell() == 5

    @pytest.mark.parametrize("terminated", ["missing", False])
    def test_a_chunked_body_is_not_read_from_an_unterminated_input(self, app, terminated):
        """PEP 3333 doesn't promise that `wsgi.input` ends with the body: a
        server that passes the socket on would block, or give the chunk
        framing as the body."""
        _route(app, "/form", Form.create, method="POST")
        environ = make_environ(
            "/form",
            method="POST",
            body=b"name=ada",
            headers=[
                ("content-type", "application/x-www-form-urlencoded"),
                ("transfer-encoding", "chunked"),
            ],
        )
        if terminated == "missing":
            del environ["wsgi.input_terminated"]
        else:
            environ["wsgi.input_terminated"] = terminated

        status, _, _ = call(app, environ)

        assert SEEN["form"] == {}
        assert environ["wsgi.input"].tell() == 0
        assert status == "200 OK"

    @pytest.mark.parametrize(
        "content_type, body, expected",
        [
            # Invalid UTF-8.
            ("application/x-www-form-urlencoded", b"name=\xff", "400 Bad Request"),
            ("application/json", b'{"name": "\xff"}', "400 Bad Request"),
            # Unknown charset.
            ("application/json; charset=nope", b"{}", "415 Unsupported Media Type"),
            (
                "application/x-www-form-urlencoded; charset=idna",
                b"a=%ff",
                "415 Unsupported Media Type",
            ),
            # JSON that Python can't read: too many digits, too deep.
            pytest.param(
                "application/json", b"1" * 5000, "400 Bad Request", id="long-int"
            ),
            pytest.param(
                "application/json",
                b"[" * 100_000 + b"]" * 100_000,
                "400 Bad Request",
                id="deep-arrays",
            ),
            # A JSON value that is not an object.
            ("application/json", b"[1, 2]", "200 OK"),
            # A multipart framing error.
            (
                "multipart/form-data; boundary=x",
                b"--x\r\nbad header\r\n\r\n--x--",
                "400 Bad Request",
            ),
        ],
    )
    def test_bad_bodies_are_client_errors(self, app, content_type, body, expected):
        _route(app, "/form", Form.create, method="POST")
        environ = make_environ(
            "/form",
            method="POST",
            body=body,
            headers=[
                ("content-type", content_type),
                ("content-length", str(len(body))),
            ],
        )

        status, _, _ = call_on_a_small_stack(app, environ)

        assert status == expected

    def test_the_media_type_is_case_insensitive(self, app):
        _route(app, "/form", Form.create, method="POST")
        body = b"--x\r\nContent-Disposition: form-data; name=name\r\n\r\nada\r\n--x--\r\n"
        environ = make_environ(
            "/form",
            method="POST",
            body=body,
            headers=[
                ("content-type", "Multipart/Form-Data; Boundary=x"),
                ("content-length", str(len(body))),
            ],
        )

        status, _, _ = call(app, environ)

        assert SEEN["form"] == {"name": "ada"}
        assert status == "200 OK"

    def test_a_malformed_accept_is_ignored(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo", headers=[("accept", "text/html;level;q=abc")])

        status, _, _ = call(app, environ)

        assert status == "200 OK"
        assert SEEN["request"].format == "html"

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

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("/files/..", "404 Not Found"),
            ("/files/.", "404 Not Found"),
            ("/files/.env", "200 OK"),
        ],
    )
    def test_a_dot_segment_value_does_not_match(self, app, url, expected):
        """A client that doesn't remove dot segments (`curl --path-as-is`)
        gets a 404: `url_for` can't build a URL with such a value."""
        _route(app, "/files/:name", Echo.index)
        status, _, _ = call(app, make_environ(url))
        assert status == expected

    def test_missing_addresses_are_none(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo")
        del environ["SERVER_NAME"], environ["REMOTE_ADDR"]
        call(app, environ)
        assert SEEN["request"].server is None
        assert SEEN["request"].client is None

    @pytest.mark.parametrize(
        "server_name, server_port",
        [
            ("0.0.0.0", "2300"),  # `proper run` on every address
            ("::", "2300"),
            ("/run/app.sock", ""),  # `proper run` on a Unix socket
        ],
    )
    def test_the_host_is_the_host_header(self, app, server_name, server_port):
        """`SERVER_NAME` is where the server listens, not the name the
        client asked for: a route for a host must match the `Host`."""
        app.router.add_route(
            Route(method="GET", path="/echo", to=Echo.index, host="api.example.com")
        )
        environ = make_environ("/echo")
        environ.update(
            {
                "SERVER_NAME": server_name,
                "SERVER_PORT": server_port,
                "HTTP_HOST": "api.example.com:8443",
            }
        )

        status, _, _ = call(app, environ)

        assert status == "200 OK"
        request = SEEN["request"]
        assert (request.host, request.port) == ("api.example.com", 8443)
        assert request.host_with_port == "api.example.com:8443"

    def test_without_a_host_header_the_host_is_the_server(self, app):
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo")
        del environ["HTTP_HOST"]
        environ.update({"SERVER_NAME": "10.0.0.5", "SERVER_PORT": "2300"})

        call(app, environ)

        assert (SEEN["request"].host, SEEN["request"].port) == ("10.0.0.5", 2300)

    @pytest.mark.parametrize(
        "host", ["example.com/x?y=1", "exa mple.com", "a@b", "[abc]", "[127.0.0.1]:81"]
    )
    def test_an_invalid_host_header_is_a_400(self, app, host):
        """The server passes the `Host` header as the client sent it."""
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo", headers=[("host", host)])

        status, _, _ = call(app, environ)

        assert status == "400 Bad Request"

    @pytest.mark.parametrize(
        "host",
        [
            "a.com,b.com",  # Bearings: `Host: a.com` and `Host: b.com`
            "a.com,a.com",  # two identical `Host` lines
            "a.com, b.com",  # one line with two values
        ],
    )
    def test_more_than_one_host_is_a_400(self, app, host):
        """RFC 9112 §3.2: a request with more than one `Host` line is a 400.
        The server joins the lines with a comma, so a comma is refused."""
        _route(app, "/echo", Echo.index)
        environ = make_environ("/echo", headers=[("host", host)])

        status, _, _ = call(app, environ)

        assert status == "400 Bad Request"

    @pytest.mark.parametrize(
        "remote_addr, remote_ip, is_secure",
        [
            # A proxy in the default TRUSTED_PROXIES: its headers are used.
            ("127.0.0.1", "198.51.100.7", True),
            ("10.0.0.9", "198.51.100.7", True),
            # A server on a Unix socket gives no peer address (gunicorn) or
            # `unix:...`: only a process on the same machine can connect.
            ("", "198.51.100.7", True),
            ("unix:/run/app.sock", "198.51.100.7", True),
            # Any other peer: the headers are ignored.
            ("203.0.113.5", "203.0.113.5", False),
        ],
    )
    def test_forwarding_headers_count_only_from_a_trusted_peer(
        self, app, remote_addr, remote_ip, is_secure
    ):
        _route(app, "/echo", Echo.index)
        environ = make_environ(
            "/echo",
            client=(remote_addr, "5555"),
            headers=[
                ("x-forwarded-for", "6.6.6.6, 198.51.100.7"),
                ("x-forwarded-proto", "https"),
            ],
        )

        call(app, environ)

        request = SEEN["request"]
        assert request.remote_ip == remote_ip
        assert request.is_secure is is_secure

    def test_trusted_proxies_set_after_the_app_was_created(self, app):
        """A list of strings set at runtime is parsed when it is used."""
        _route(app, "/echo", Echo.index)
        trusted = app.config.TRUSTED_PROXIES
        app.config.TRUSTED_PROXIES = ["203.0.113.5"]
        try:
            for peer, remote_ip in [
                ("203.0.113.5", "198.51.100.7"),
                ("10.0.0.9", "10.0.0.9"),
            ]:
                environ = make_environ(
                    "/echo",
                    client=(peer, "5555"),
                    headers=[
                        ("x-forwarded-for", "198.51.100.7"),
                        ("x-forwarded-proto", "https"),
                    ],
                )
                status, _, _ = call(app, environ)
                assert status == "200 OK"
                assert SEEN["request"].remote_ip == remote_ip
        finally:
            app.config.TRUSTED_PROXIES = trusted

    def test_an_unknown_status_has_no_reason(self, app):
        from proper.core.app_wsgi import _reason

        assert _reason(299) == ""


@pytest.fixture(autouse=True)
def _reset_current():
    yield
    current.request = None
    current.response = None


class Whoami(Controller):
    def index(self):
        if self.request.headers.get("x-user"):
            current.user = self.request.headers["x-user"]
        return self.render(text=str(current.user))


class TestContextPerRequest:
    """The server runs many requests on each thread: what one request sets in
    `current` must not be there for the next one on the same thread."""

    def test_current_does_not_leak_between_requests(self, app):
        _route(app, "whoami", Whoami.index)
        _, _, body = call(app, make_environ("/whoami", headers=[("x-user", "alice")]))
        assert b"".join(body) == b"alice"
        _, _, body = call(app, make_environ("/whoami"))
        assert b"".join(body) == b"None"
        assert current.user is None
