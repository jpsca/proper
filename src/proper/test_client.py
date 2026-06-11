import asyncio
import mimetypes
import secrets
import typing as t
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

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
from .helpers import CIMultiDict, DotDict, jsonplus
from .helpers.asgi import make_test_scope


if t.TYPE_CHECKING:
    from .app import App


__all__ = ("TestClient",)


def _to_bytes(value, charset="latin1"):
    if isinstance(value, str):
        return value.encode(charset)
    return value


class TestClient:
    """Test client that drives the app through the full ASGI stack,
    exactly as they would in production.

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

        scope = make_test_scope(
            url,
            method=method,
            params=params,
            headers=req_headers.items()
        )

        resp_status = 0
        resp_headers = CIMultiDict()
        body_parts: list[bytes] = []
        body_consumed = False

        async def receive():
            nonlocal body_consumed
            if not body_consumed:
                body_consumed = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            # Block until disconnect - shouldn't normally be reached
            await asyncio.Event().wait()

        async def send(message):
            nonlocal resp_status
            if message["type"] == "http.response.start":
                resp_status = message["status"]
                for raw_name, raw_val in message.get("headers", []):
                    name = (
                        raw_name.decode("latin-1")
                        if isinstance(raw_name, bytes)
                        else raw_name
                    )
                    val = (
                        raw_val.decode("latin-1")
                        if isinstance(raw_val, bytes)
                        else raw_val
                    )
                    resp_headers[name] = val
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    body_parts.append(chunk)

        asyncio.run(self.app(scope, receive, send))

        resp_body = b"".join(body_parts)

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


class WebSocketTestSession:
    """Async helper for testing WebSocket channels.

    Arguments:
        app: The Proper `App` instance.
        path: The WebSocket path (defaults to `/cable`).
    """

    def __init__(self, app: "App", path: str) -> None:
        self.app = app
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._path = path

    async def connect(self) -> asyncio.Task:
        """Start the WebSocket handler as a background task.

        Returns the task so you can `await` it after `close()`.
        """
        scope = {
            "type": "websocket",
            "path": self._path,
            "scheme": "ws",
            "server": ("example.com", 80),
            "headers": [],
            "query_string": b"",
        }
        task = asyncio.create_task(self.app(scope, self._receive, self._send))
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
        msg = await asyncio.wait_for(self._from_app.get(), timeout=timeout)
        if msg.get("type") == "websocket.send":
            return jsonplus.loads(msg["text"])
        return msg

    async def receive_raw(self, timeout: float = 1.0) -> dict:
        """Receive the next raw ASGI message from the app."""
        return await asyncio.wait_for(self._from_app.get(), timeout=timeout)

    def client_send(self, data: dict) -> None:
        """Queue a JSON message from the client to the app."""
        self._to_app.put_nowait(
            {
                "type": "websocket.receive",
                "text": jsonplus.dumps(data),
            }
        )

    def client_send_raw(self, msg: dict) -> None:
        """Queue a raw ASGI message to the app."""
        self._to_app.put_nowait(msg)

    async def close(self) -> None:
        """Disconnect the client."""
        self._to_app.put_nowait({"type": "websocket.disconnect"})

    async def _receive(self):
        return await self._to_app.get()

    async def _send(self, msg):
        await self._from_app.put(msg)


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
