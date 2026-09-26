import asyncio
import enum
import mimetypes
import secrets
import typing as t
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlparse

from .constants import (
    AUTH_COOKIE_NAME,
    AUTH_COOKIE_SALT,
    DELETE,
    GET,
    HEAD,
    OPTIONS,
    PATCH,
    POST,
    PUT,
    QUERY,
)
from .core.request import Request
from .helpers import CIMultiDict, DotDict, jsonplus


if t.TYPE_CHECKING:
    from .app import App


__all__ = (
    "TestClient",
    "make_test_request",
    "make_test_scope",
    "make_test_ws_scope",
    "HttpProtocolStub",
    "WsProtocolStub",
)


class _Sentinel(enum.Enum):
    FROM_URL = enum.auto()


_FROM_URL = _Sentinel.FROM_URL

SCHEME_DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}


def _header_pairs(
    headers: "dict[str, str] | t.Iterable[tuple[str, str]] | None",
) -> list[tuple[str, str]]:
    if isinstance(headers, dict):
        return [(str(name), str(value)) for name, value in headers.items()]
    return list(headers or [])


def make_test_request(
    url: str = "/",
    *,
    method: str = GET,
    params: dict | None = None,
    headers: "dict[str, str] | t.Iterable[tuple[str, str]] | None" = None,
    app: "App | None" = None,
    client: "tuple[str, int | None] | None" = None,
    server: "tuple[str, int | None] | None | t.Literal[_Sentinel.FROM_URL]" = _FROM_URL,
    http_version: str = "1.1",
    request_cls: type[Request] = Request,
) -> Request:
    """Build a `Request` the way the server would, from a URL.

    The URL may carry a scheme, a host and port, a path and a query string.
    `params`, if given, replace the query string. A `host` header is added
    unless `headers` already has one. `server` overrides the `(host, port)`
    taken from the URL.
    """
    upa = urlparse(url)
    scheme = upa.scheme or "http"
    path = upa.path or "/"

    if ":" in upa.netloc:
        host, port_str = upa.netloc.rsplit(":", 1)
        port = int(port_str)
    else:
        host = upa.netloc or "example.com"
        port = SCHEME_DEFAULT_PORTS.get(scheme, 80)

    query_string = urlencode(params) if params else (upa.query or "")

    pairs = _header_pairs(headers)
    if not any(name.lower() == "host" for name, _ in pairs):
        pairs.insert(0, ("host", upa.netloc or host))

    return request_cls(
        method=method,
        path=path,
        query_string=query_string,
        headers=pairs,
        scheme=scheme,
        server=(host, port) if server is _FROM_URL else server,
        client=client,
        http_version=http_version,
        app=app,
    )


def _body_reader(body: bytes):
    async def read() -> bytes:
        return body

    return read


def make_test_scope(
    url: str = "/",
    *,
    method: str = GET,
    headers: "dict[str, str] | t.Iterable[tuple[str, str]] | None" = None,
    client: str = "127.0.0.1:1234",
) -> SimpleNamespace:
    """A stand-in for the server's HTTP scope, for driving `app.__rsgi__`
    directly."""
    upa = urlparse(url)
    scheme = upa.scheme or "http"
    netloc = upa.netloc or "example.com"
    pairs = _header_pairs(headers)
    if not any(name.lower() == "host" for name, _ in pairs):
        pairs.insert(0, ("host", netloc))
    if ":" not in netloc:
        netloc = f"{netloc}:{SCHEME_DEFAULT_PORTS.get(scheme, 80)}"
    return SimpleNamespace(
        proto="http",
        method=method.upper(),
        path=upa.path or "/",
        query_string=upa.query or "",
        headers=_HeadersStub(pairs),
        scheme=scheme,
        server=netloc,
        client=client,
        http_version="1.1",
    )


class _HeadersStub:
    def __init__(self, pairs):
        self._pairs = pairs

    def items(self):
        return list(self._pairs)


class HttpProtocolStub:
    """Stands in for the server's HTTP protocol object: hands the app the
    request body and records what it sends back in `status`, `headers`,
    `body` and `file`."""

    def __init__(self, body: bytes = b"") -> None:
        self._body = body
        self.status: int = 0
        self.headers: list[tuple[str, str]] = []
        self.body = b""
        self.file: str | None = None
        self.streamed = False

    async def __call__(self) -> bytes:
        return self._body

    def response_empty(self, status, headers) -> None:
        self.status, self.headers = status, list(headers)

    def response_str(self, status, headers, body: str) -> None:
        self.status, self.headers, self.body = status, list(headers), body.encode()

    def response_bytes(self, status, headers, body: bytes) -> None:
        self.status, self.headers, self.body = status, list(headers), body

    def response_file(self, status, headers, path: str) -> None:
        self.status, self.headers, self.file = status, list(headers), path

    async def response_stream(self, status, headers) -> "HttpProtocolStub":
        self.status, self.headers, self.streamed = status, list(headers), True
        return self

    async def send_bytes(self, data: bytes) -> None:
        self.body += data

    async def send_str(self, data: str) -> None:
        self.body += data.encode()


def _to_bytes(value, charset="latin1"):
    if isinstance(value, str):
        return value.encode(charset)
    return value


class TestClient:
    """Test client that drives requests through the whole pipeline, the
    same way the server does.

    Arguments:
        app: The Proper `App` instance to test.

    Example::

        client = TestClient(app)
        result = client.get("/hello")
        assert result.status == 200

    """

    __test__ = False  # prevent pytest collection

    default_headers: dict[str, str]
    remote_ip: str = "127.0.0.1"
    user_agent: str = "TestClient"

    def __init__(
        self,
        app: "App",
        *,
        headers: dict[str, str] | None = None,
        sync: bool = True,
    ) -> None:
        self.app = app

        headers = {key.lower(): value for key, value in headers.items()} if headers else {}
        headers.setdefault("forwarded", f"for={self.remote_ip};")
        headers.setdefault("user-agent", self.user_agent)
        self.default_headers = headers

        # Runs requests inline, so a request shares this thread's connection:
        # one transaction spans the test and the requests it makes.
        self.app.config.RUN_SYNC = sync

    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(url, method=GET, params=params, headers=headers)

    def head(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(url, method=HEAD, params=params, headers=headers)

    def post(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(
            url, method=POST, body=body, upload_files=upload_files, headers=headers
        )

    def patch(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(
            url, method=PATCH, body=body, upload_files=upload_files, headers=headers
        )

    def put(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(
            url, method=PUT, body=body, upload_files=upload_files, headers=headers
        )

    def query(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(
            url, method=QUERY, body=body, upload_files=upload_files, headers=headers
        )

    def options(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(url, method=OPTIONS, params=params, headers=headers)

    def delete(
        self,
        url: str,
        *,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict | None = None,
    ) -> DotDict:
        return self._request(
            url, method=DELETE, body=body, upload_files=upload_files, headers=headers
        )

    def websocket(self, url: str = "") -> "WebSocketTestSession":
        """Create a WebSocket test session.

        Usage:

            ws = client.websocket()
            task = await ws.connect()
            await ws.subscribe("ChatChannel", room="general")
            confirm = await ws.receive()
            await ws.send_action("ChatChannel", "speak", {"text": "hi"})
            msg = await ws.receive()
            await ws.close()
            await task
        """
        path = url or self.app.config.get("CABLE_PATH", "/cable")
        return WebSocketTestSession(self.app, path)

    def sign_in(self, session):
        """Adds an authenticated session cookie to the client, for testing authenticated endpoints."""
        value = self.app.dumps(session.token, salt=AUTH_COOKIE_SALT)
        self.default_headers["cookie"] = f"{AUTH_COOKIE_NAME}={value}"

    # ---- Private ----

    def _request(
        self,
        url: str,
        *,
        method=GET,
        params: dict | None = None,
        body: dict | str | bytes | BytesIO = b"",
        upload_files: list[tuple[str, str | Path]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> DotDict:
        if params is None:
            params = {}

        req_headers = dict(self.default_headers.items())
        headers = {key.lower(): value for key, value in headers.items()} if headers else {}
        req_headers.update(headers)

        if upload_files:
            if body and not isinstance(body, dict):
                raise ValueError(
                    "When using upload_files, body must be a dict of form fields."
                )
            body = t.cast(dict, body or {})
            content_type, body_bytes = _encode_multipart(
                params=body, upload_files=upload_files
            )
            req_headers["content-type"] = content_type
        else:
            body_bytes = _encode_body(body)
            if isinstance(body, dict) and body:
                req_headers["content-type"] = "application/x-www-form-urlencoded"

        if body_bytes:
            req_headers["content-length"] = str(len(body_bytes))

        request = make_test_request(
            url,
            method=method,
            params=params,
            headers=req_headers,
            app=self.app,
            request_cls=self.app.request_cls,
        )
        response = asyncio.run(self.app._respond(request, _body_reader(body_bytes)))

        resp_status, raw_headers, raw_body = response.prepare(request)
        resp_headers = CIMultiDict(raw_headers)
        if isinstance(raw_body, bytes):
            resp_body = raw_body
        else:
            try:
                resp_body = b"".join(bytes(chunk) for chunk in raw_body)
            finally:
                body_close = getattr(raw_body, "close", None)
                if callable(body_close):
                    body_close()

        # Parse content-type header
        ct = resp_headers.get("content-type", "")
        mimetype = ct.split(";")[0].strip() if ct else ""
        charset = "utf-8"
        if "charset=" in ct:
            charset = ct.split("charset=")[-1].strip().split(";")[0].strip()

        body_str = resp_body.decode(charset) if resp_body else ""

        result = DotDict(
            status=resp_status,
            body=body_str,
            mimetype=mimetype,
            content_type=ct,
        )
        dict.__setitem__(result, "headers", resp_headers)
        return result


def make_test_ws_scope(path: str = "/cable") -> SimpleNamespace:
    """A stand-in for the server's WebSocket scope."""
    return SimpleNamespace(
        proto="ws",
        method="GET",
        path=path,
        query_string="",
        headers={},
        scheme="ws",
        server="example.com:80",
        client="127.0.0.1:1234",
        http_version="1.1",
    )


class WsMessage:
    """What the server hands over for each frame: a `kind` (0 close,
    1 bytes, 2 text) and its `data`."""

    def __init__(self, kind: int, data: "bytes | str | None" = None) -> None:
        self.kind = kind
        self.data = data


class WsProtocolStub:
    """Stands in for the server's WebSocket protocol object.

    Frames from the client are queued with `client_send`; what the app
    sends to the client, and whether it accepted or closed, come out of
    `from_app` as dicts: `{"type": "accept"}`, `{"type": "text", "text": ...}`,
    `{"type": "close", "code": ...}`.
    """

    def __init__(self) -> None:
        self.to_app: asyncio.Queue = asyncio.Queue()
        self.from_app: asyncio.Queue = asyncio.Queue()

    # -- server side, called by the app --

    async def accept(self) -> "WsProtocolStub":
        await self.from_app.put({"type": "accept"})
        return self

    def close(self, code: int) -> None:
        self.from_app.put_nowait({"type": "close", "code": code})

    async def receive(self) -> WsMessage:
        return await self.to_app.get()

    async def send_str(self, text: str) -> None:
        await self.from_app.put({"type": "text", "text": text})

    async def send_bytes(self, data: bytes) -> None:
        await self.from_app.put({"type": "bytes", "bytes": data})

    # -- client side, called by the test --

    def client_send(self, data: dict) -> None:
        """Queue a JSON message from the client to the app."""
        self.to_app.put_nowait(WsMessage(2, jsonplus.dumps(data)))

    def client_send_text(self, text: str) -> None:
        self.to_app.put_nowait(WsMessage(2, text))

    def client_send_bytes(self, data: bytes) -> None:
        self.to_app.put_nowait(WsMessage(1, data))

    def client_disconnect(self) -> None:
        self.to_app.put_nowait(WsMessage(0))

    async def client_recv(self, timeout: float = 1.0) -> dict:
        """The next thing the app sent to the client."""
        return await asyncio.wait_for(self.from_app.get(), timeout=timeout)


class WebSocketTestSession:
    """Async helper for testing WebSocket channels.

    Arguments:
        app: The Proper `App` instance.
        path: The WebSocket path (defaults to `/cable`).
    """

    def __init__(self, app: "App", path: str) -> None:
        self.app = app
        self.protocol = WsProtocolStub()
        self._path = path

    async def connect(self) -> asyncio.Task:
        """Start the WebSocket handler as a background task.

        Returns the task so you can `await` it after `close()`.
        """
        scope = make_test_ws_scope(self._path)
        task = asyncio.create_task(self.app.__rsgi__(scope, self.protocol))
        # Wait for the accept/reject
        await asyncio.sleep(0.01)
        return task

    async def subscribe(self, channel: str, **params) -> dict:
        """Send a subscribe command and return the response."""
        self.client_send(
            {
                "command": "subscribe",
                "channel": channel,
                "params": params or {},
            }
        )
        return await self.receive()

    async def send_action(
        self, channel: str, action: str, data: dict | None = None, **params
    ) -> None:
        """Send a message/action to a subscribed channel."""
        self.client_send(
            {
                "command": "message",
                "channel": channel,
                "action": action,
                "data": data or {},
                "params": params or {},
            }
        )

    async def unsubscribe(self, channel: str, **params) -> None:
        """Send an unsubscribe command."""
        self.client_send(
            {
                "command": "unsubscribe",
                "channel": channel,
                "params": params or {},
            }
        )

    async def receive(self, timeout: float = 1.0) -> dict:
        """Receive the next message from the app, parsed from JSON."""
        msg = await self.protocol.client_recv(timeout=timeout)
        if msg.get("type") == "text":
            return jsonplus.loads(msg["text"])
        return msg

    async def receive_raw(self, timeout: float = 1.0) -> dict:
        """Receive the next raw event from the app: an accept, a close, or
        a frame as sent."""
        return await self.protocol.client_recv(timeout=timeout)

    def client_send(self, data: dict) -> None:
        """Queue a JSON message from the client to the app."""
        self.protocol.client_send(data)

    def client_send_text(self, text: str) -> None:
        """Queue a raw text frame from the client to the app."""
        self.protocol.client_send_text(text)

    async def close(self) -> None:
        """Disconnect the client."""
        self.protocol.client_disconnect()


# --- encoding helpers ---


def _encode_body(body: dict | str | bytes | BytesIO) -> bytes:
    if isinstance(body, dict):
        return urlencode(body).encode("utf-8") if body else b""
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, BytesIO):
        return body.read()
    return body


def _encode_multipart(
    params: dict | None = None,
    upload_files: list[tuple[str, str | Path]] | None = None,
) -> tuple[str, bytes]:
    boundary = b"----------b_o_u_n_d_a_r_y" + secrets.token_hex(16).encode() + b"$"
    lines: list[bytes] = []

    def _append_file(skey: str, filename: str | Path):
        key = skey.encode("ascii")
        filepath = Path(filename)

        ftype = mimetypes.guess_type(filename)[0]
        ctype = _to_bytes(ftype) if ftype else b"application/octet-stream"

        lines.extend(
            [
                b"--" + boundary,
                b"Content-Disposition: form-data; "
                + b'name="'
                + key
                + b'"; filename="'
                + _to_bytes(str(filename))
                + b'"',
                b"Content-Type: " + ctype,
                b"",
                filepath.read_bytes(),
            ]
        )

    params = params or {}
    for key, value in params.items():
        if isinstance(key, str):
            key = key.encode("ascii")

        if isinstance(value, int):
            value = str(value).encode("utf8")
        elif isinstance(value, str):
            value = value.encode("utf8")
        elif not isinstance(value, (bytes, str)):
            raise ValueError(
                (
                    "Value for field {} is a {} ({}). It must be str, bytes or an int"
                ).format(key, type(value), value)
            )
        lines.extend(
            [
                b"--" + boundary,
                b'Content-Disposition: form-data; name="' + key + b'"',
                b"",
                value,
            ]
        )

    if upload_files:
        for key, filename in upload_files:
            _append_file(key, filename)

    lines.extend([b"--" + boundary + b"--", b""])
    body = b"\r\n".join(lines)
    content_type = "multipart/form-data; boundary=%s" % boundary.decode("ascii")
    return content_type, body
