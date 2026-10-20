"""`App._bearings`: the app as Bearings' raw interface calls it, with the head
Bearings parsed instead of a WSGI environ."""
import http.client
import io
import socket

import pytest
from bearings import Listener, Server
from bearings.wsgi import WsgiHandler

from proper import Controller
from proper.router import Route


SEEN: dict = {}


class Echo(Controller):
    def index(self):
        SEEN["request"] = self.request
        return self.render(text="ok")

    def create(self):
        SEEN["form"] = dict(self.request.form)
        return self.render(text="saved")


class Files(Controller):
    def show(self):
        self.response.send_file(SEEN["path"])


def make_head(path="/", query="", *, method="GET", headers=(), client=("10.0.0.9", "5555")):
    """A head the way Bearings sends it: fields ended by NUL."""
    fields = [method, path, query, "HTTP/1.1", *client]
    for name, value in headers:
        fields += [name, value]
    return "".join(field + "\0" for field in fields)


LISTENER = Listener("127.0.0.1", 2300, "http")

HEADS = [
    make_head(),
    make_head("/echo", "a=1&b=%20", headers=[("Host", "example.com:8080")]),
    # percent-escapes in the path; the same as a raw UTF-8 path
    make_head("/a%20b/%C3%B1", headers=[("Host", "x")]),
    make_head("/a b/" + "ñ".encode().decode("latin-1"), headers=[("Host", "x")]),
    # a byte that is not UTF-8
    make_head("/%FF", headers=[("Host", "x")]),
    # names as the client wrote them; repeated lines; a name with `_`
    make_head(
        "/h",
        headers=[
            ("HOST", "Example.com"), ("Accept", "a"), ("accept", "b"), ("Cookie", "a=1"),
            ("cookie", "b=2"), ("X_Forwarded_For", "1.2.3.4"), ("Content-Type", "text/plain"),
            ("Content-Length", "0"), ("User-Agent", "test"),
        ],
    ),
    # from a trusted proxy, the forwarded headers count
    make_head(
        "/p",
        headers=[("Host", "a.com"), ("X-Forwarded-For", "198.51.100.7"),
                 ("X-Forwarded-Proto", "https")],
        client=("127.0.0.1", "40000"),
    ),
    # a Unix socket: no client address
    make_head("/u", headers=[("Host", "x")], client=("", "")),
]


def as_bytes(head):
    return head.encode("latin-1")


class TestTheSameRequestAsWsgi:
    """The request built from the head is the one WSGI builds from the
    environ pybearings makes of the same head."""

    @pytest.mark.parametrize("head", HEADS)
    def test_same_request(self, app, head):
        handler = WsgiHandler(app, host=LISTENER.name, url_scheme=LISTENER.url_scheme)
        handler.listening_on(LISTENER.port)
        from_environ = app._request_from_environ(handler.environ(as_bytes(head)))
        from_head = app._request_from_head(head.split("\0"), LISTENER)

        for attr in (
            "method", "path", "query", "scheme", "protocol", "server", "client", "http_version",
            "server_software", "host", "port", "content_type", "content_length", "remote_ip",
            "cookies", "user_agent",
        ):
            assert getattr(from_head, attr) == getattr(from_environ, attr), attr
        assert dict(from_head.headers.items()) == dict(from_environ.headers.items())

    def test_without_a_listening_name_there_is_no_server(self, app):
        request = app._request_from_head(make_head().split("\0"), Listener("", None, "http"))
        assert request.server is None

    def test_an_empty_path_is_the_root(self, app):
        request = app._request_from_head(make_head("").split("\0"), LISTENER)
        assert request.path == "/"


class TestTheResponse:
    def test_status_headers_and_body(self, app):
        app.router.add_route(Route("GET", "/echo", to=Echo.index))
        status, headers, body = app._bearings(
            make_head("/echo", headers=[("Host", "x")]), io.BytesIO(), LISTENER
        )
        assert status == 200
        assert ("content-type", "text/plain; charset=utf-8") in [
            (name.lower(), value) for name, value in headers
        ]
        assert body == b"ok"

    def test_the_request_id_is_sent_back(self, app):
        app.router.add_route(Route("GET", "/echo", to=Echo.index))
        _, headers, _ = app._bearings(
            make_head("/echo", headers=[("Host", "x"), ("X-Request-ID", "abc-123")]),
            io.BytesIO(),
            LISTENER,
        )
        assert ("x-request-id", "abc-123") in [
            (name.lower(), value) for name, value in headers
        ]

    def test_the_body_is_read(self, app):
        app.router.add_route(Route("POST", "/echo", to=Echo.create))
        body = b"name=Ana"
        head = make_head("/echo", method="POST", headers=[
            ("Host", "x"), ("Content-Type", "application/x-www-form-urlencoded"),
            ("Content-Length", str(len(body))),
        ])
        status, _, sent = app._bearings(head, io.BytesIO(body), LISTENER)
        assert (status, sent) == (200, b"saved")
        assert SEEN["form"] == {"name": "Ana"}

    def test_an_invalid_host_is_a_400(self, app):
        app.router.add_route(Route("GET", "/echo", to=Echo.index))
        status, _, _ = app._bearings(
            make_head("/echo", headers=[("Host", "a@b")]), io.BytesIO(), LISTENER
        )
        assert status == 400


class TestOnBearings:
    """Served by a running Bearings, as `proper run` does."""

    @pytest.fixture()
    def server(self, app):
        app.router.add_route(Route("GET", "/echo", to=Echo.index))
        app.router.add_route(Route("POST", "/echo", to=Echo.create))
        app.router.add_route(Route("GET", "/file", to=Files.show))
        server = Server(app._bearings, raw=True, host="127.0.0.1", loops=1, workers=2)
        with server:
            yield server

    def request(self, server, method="GET", path="/", body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            response.body = response.read()
            return response
        finally:
            conn.close()

    def test_a_request(self, server):
        response = self.request(server, "GET", "/echo?x=1", headers={"Cookie": "a=1"})
        assert (response.status, response.body) == (200, b"ok")
        request = SEEN["request"]
        assert (request.path, request.query["x"], request.cookies["a"]) == ("/echo", "1", "1")
        assert request.client[0] == "127.0.0.1"
        assert request.server == ("127.0.0.1", server.port)
        assert request.server_software.startswith("bearings/")

    def test_a_form(self, server):
        response = self.request(
            server, "POST", "/echo", body=b"name=Ana",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert (response.status, response.body) == (200, b"saved")
        assert SEEN["form"] == {"name": "Ana"}

    def test_head_sends_headers_only(self, server):
        response = self.request(server, "HEAD", "/echo")
        assert (response.status, response.body) == (200, b"")

    def test_a_file(self, server, tmp_path):
        path = tmp_path / "f.txt"
        path.write_bytes(b"file body")
        SEEN["path"] = path
        response = self.request(server, "GET", "/file")
        assert (response.status, response.body) == (200, b"file body")

    def test_not_found(self, server):
        assert self.request(server, "GET", "/nope").status == 404

    def test_two_host_lines_are_a_400(self, server):
        with socket.create_connection(("127.0.0.1", server.port), timeout=10) as sock:
            sock.sendall(
                b"GET /echo HTTP/1.1\r\nHost: a.com\r\nHost: b.com\r\nConnection: close\r\n\r\n"
            )
            answer = b""
            while chunk := sock.recv(4096):
                answer += chunk
        assert answer.startswith(b"HTTP/1.1 400 ")
