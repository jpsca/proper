import json
from io import BytesIO

import pytest

from proper.errors import (
    BadRequest,
    ClientDisconnected,
    MultipartError,
    RequestEntityTooLarge,
    UnsupportedMediaType,
)
from proper.test_client import make_test_request


def _build_multipart(parts, boundary="testboundary"):
    body = b""
    for part in parts:
        body += f"--{boundary}\r\n".encode()
        disp = f'Content-Disposition: form-data; name="{part["name"]}"'
        if "filename" in part:
            disp += f'; filename="{part["filename"]}"'
        body += disp.encode() + b"\r\n"
        if "content_type" in part:
            body += f'Content-Type: {part["content_type"]}\r\n'.encode()
        body += b"\r\n"
        value = part["value"]
        if isinstance(value, str):
            value = value.encode()
        body += value + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body


def _reader(body: bytes):
    """Stand-in for the server's body reader (WSGI's `wsgi.input.read`)."""
    def read(size):
        return body

    return read


def _post(app, body: bytes, content_type="application/json", method="POST"):
    return make_test_request("/", method=method, app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", content_type),
    ])


def test_read_body(app):
    body = b'{"a": 1}'
    req = _post(app, body)
    req._read_body_sync(_reader(body))
    assert req.body == body
    assert req.form["a"] == 1


def test_read_body_over_max_content_length_is_refused_before_reading(app):
    app.config.MAX_CONTENT_LENGTH = 5
    body = b"toolongbody"
    req = _post(app, body)
    reads = []

    def read(size):
        reads.append(True)
        return body

    with pytest.raises(RequestEntityTooLarge):
        req._read_body_sync(read)
    assert reads == []
    app.config.MAX_CONTENT_LENGTH = 0


def test_read_body_error_propagates(app):
    req = _post(app, b"0123456789")

    def read(size):
        raise ClientDisconnected()

    with pytest.raises(ClientDisconnected):
        req._read_body_sync(read)


def test_read_body_shorter_than_content_length(app):
    req = _post(app, b"0123456789")
    with pytest.raises(BadRequest, match="Content-Length"):
        req._read_body_sync(_reader(b"01234"))


def test_parse_body_bytes_get_skips(app):
    req = make_test_request("/", method="GET", app=app, headers=[
        ("content-type", "application/json"),
    ])
    req._parse_body_bytes(b'{"a": 1}')
    assert req.body == b""
    assert len(req.form) == 0


def test_parse_body_bytes_over_max_content_length(app):
    app.config.MAX_CONTENT_LENGTH = 5
    req = _post_chunked(app, "text/plain")
    with pytest.raises(RequestEntityTooLarge):
        req._parse_body_bytes(b"0123456789")


def test_parse_body_get_skips(app):
    req = make_test_request("/", method="GET", app=app)
    req._read_body_sync(_reader(b""))
    assert len(req.form) == 0

def test_parse_body_head_skips(app):
    req = make_test_request("/", method="HEAD", app=app)
    req._read_body_sync(_reader(b""))
    assert len(req.form) == 0

def test_parse_body_no_content_length_skips(app):
    """In HTTP/1.1, a request with neither `content-length` nor
    `transfer-encoding` has no body (RFC 9112 §6.3)."""
    req = make_test_request("/", method="POST", app=app)
    reads = []

    def read(size):
        reads.append(size)
        return b"name=Jon"

    req._read_body_sync(read)
    assert reads == []
    assert len(req.form) == 0

def test_parse_body_json(app):
    body = json.dumps({"key": "value"}).encode()
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    req._read_body_sync(_reader(body))
    assert req.form.get("key") == "value"

def test_parse_body_json_charset(app):
    body = json.dumps({"x": "y"}).encode()
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json; charset=utf-8"),
    ])
    req._read_body_sync(_reader(body))
    assert req.form.get("x") == "y"

def test_parse_body_form_urlencoded(app):
    body = b"name=Jon&age=30"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-www-form-urlencoded"),
    ])
    req._read_body_sync(_reader(body))
    assert req.form.get("name") == "Jon"
    assert req.form.get("age") == "30"

def test_parse_body_form_x_url_encoded(app):
    body = b"key=val"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-url-encoded"),
    ])
    req._read_body_sync(_reader(body))
    assert req.form.get("key") == "val"

def test_parse_body_multipart(app):
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "field1", "value": "hello"}],
        boundary=boundary,
    )
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", f"multipart/form-data; boundary={boundary}"),
    ])
    req._read_body_sync(_reader(body))
    assert req.form.get("field1") == "hello"

def test_parse_body_unparsed_content_type_exposes_raw_body(app):
    """Binary or unparsed content types don't fail - the controller
    can still reach the bytes via `request.body`."""
    body = b"<root/>"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/xml"),
    ])
    req._read_body_sync(_reader(body))
    assert req.body == body
    assert len(req.form) == 0


# --- Bodies without Content-Length ---


def _chunks(body: bytes, size: int = 3):
    """A reader that returns at most `size` bytes per call, then `b""`, as
    Granian's `wsgi.input.read(n)` does for a chunked body."""
    data = BytesIO(body)

    def read(n):
        return data.read(min(n, size))

    return read


def _post_chunked(app, content_type, method="POST", headers=(), **kwargs):
    return make_test_request("/", method=method, app=app, headers=[
        ("transfer-encoding", "chunked"),
        ("content-type", content_type),
        *headers,
    ], **kwargs)


def test_read_chunked_body(app):
    body = b"name=Jon&age=30"
    req = _post_chunked(app, "application/x-www-form-urlencoded")
    req._read_body_sync(_chunks(body))
    assert req.body == body
    assert req.form.get("name") == "Jon"
    assert req.form.get("age") == "30"


def test_read_chunked_body_up_to_max_content_length(app):
    app.config.MAX_CONTENT_LENGTH = 5
    req = _post_chunked(app, "text/plain")
    req._read_body_sync(_chunks(b"12345"))
    assert req.body == b"12345"


def test_read_chunked_body_over_max_content_length(app):
    app.config.MAX_CONTENT_LENGTH = 5
    data = BytesIO(b"1234567890" * 1000)
    req = _post_chunked(app, "text/plain")
    with pytest.raises(RequestEntityTooLarge):
        req._read_body_sync(data.read)
    # It stops reading after the limit, it doesn't buffer the whole body.
    assert data.tell() == 6


def test_read_chunked_body_without_max_content_length(app):
    app.config.MAX_CONTENT_LENGTH = 0
    body = b"x" * 200_000
    req = _post_chunked(app, "text/plain")
    req._read_body_sync(BytesIO(body).read)
    assert req.body == body


def test_read_empty_chunked_body(app):
    req = _post_chunked(app, "application/json")
    req._read_body_sync(_chunks(b""))
    assert req.body == b""
    assert len(req.form) == 0


def test_read_chunked_body_get_skips(app):
    req = _post_chunked(app, "text/plain", method="GET")
    reads = []

    def read(size):
        reads.append(size)
        return b""

    req._read_body_sync(read)
    assert reads == []


def test_content_length_wins_over_reading_to_the_end(app):
    """With a `content-length`, only that many bytes are read."""
    body = b"name=Jon"
    req = _post_chunked(
        app,
        "application/x-www-form-urlencoded",
        headers=[("content-length", str(len(body)))],
    )
    req._read_body_sync(BytesIO(body + b"&extra=1").read)
    assert req.body == body


def test_read_http2_body_without_content_length(app):
    """HTTP/2 and 3 have no `transfer-encoding`: the end of the stream ends
    the body, and `content-length` is optional."""
    body = b'{"a": 1}'
    req = make_test_request("/", method="POST", app=app, http_version="2", headers=[
        ("content-type", "application/json"),
    ])
    req._read_body_sync(_chunks(body))
    assert req.form["a"] == 1


# --- Content types ---


@pytest.mark.parametrize("content_type", [
    "Multipart/Form-Data; boundary=testboundary",
    "multipart/form-data; Boundary=testboundary",
    "MULTIPART/FORM-DATA; BOUNDARY=testboundary",
])
def test_parse_body_multipart_content_type_is_case_insensitive(app, content_type):
    body = _build_multipart([{"name": "field1", "value": "hello"}])
    req = _post(app, body, content_type=content_type)
    req._read_body_sync(_reader(body))
    assert req.form.get("field1") == "hello"


@pytest.mark.parametrize("content_type", [
    "Application/JSON",
    "APPLICATION/JSON; Charset=UTF-8",
])
def test_parse_body_json_content_type_is_case_insensitive(app, content_type):
    body = b'{"a": 1}'
    req = _post(app, body, content_type=content_type)
    req._read_body_sync(_reader(body))
    assert req.form["a"] == 1


def test_parse_body_urlencoded_content_type_is_case_insensitive(app):
    body = b"a=1"
    req = _post(app, body, content_type="Application/X-WWW-Form-Urlencoded; charset=utf-8")
    req._read_body_sync(_reader(body))
    assert req.form["a"] == "1"


@pytest.mark.parametrize("body", [b"[1, 2]", b'[["a", 1]]', b'"x"', b"3", b"true", b"null"])
def test_parse_body_json_not_an_object(app, body):
    """The form only has the members of a JSON object; any other value is
    still in `request.body`."""
    req = _post(app, body)
    req._read_body_sync(_reader(body))
    assert len(req.form) == 0
    assert req.body == body


def test_parse_body_invalid_json(app):
    body = b"{nope"
    req = _post(app, body)
    with pytest.raises(MultipartError):
        req._read_body_sync(_reader(body))


def test_parse_body_urlencoded_charset(app):
    body = "name=Jos\xe9".encode("latin-1")
    req = _post(app, body, content_type="application/x-www-form-urlencoded; charset=latin-1")
    req._read_body_sync(_reader(body))
    assert req.form["name"] == "Jos\xe9"


@pytest.mark.parametrize("content_type", [
    "application/x-www-form-urlencoded",
    "application/json",
    "application/json; charset=utf-8",
])
def test_parse_body_invalid_utf8(app, content_type):
    body = b'{"name": "\xff"}' if "json" in content_type else b"name=\xff"
    req = _post(app, body, content_type=content_type)
    with pytest.raises(BadRequest, match="utf-8"):
        req._read_body_sync(_reader(body))


@pytest.mark.parametrize("content_type", [
    "application/x-www-form-urlencoded; charset=nope",
    "application/json; charset=nope",
    # A codec that is not a text encoding.
    "application/json; charset=base64",
])
def test_parse_body_unknown_charset(app, content_type):
    body = b"e30="
    req = _post(app, body, content_type=content_type)
    with pytest.raises(UnsupportedMediaType, match="charset"):
        req._read_body_sync(_reader(body))


def test_parse_body_multipart_framing_error(app):
    body = b"--testboundary\r\nbad header line\r\n\r\nv\r\n--testboundary--\r\n"
    req = _post(app, body, content_type="multipart/form-data; boundary=testboundary")
    with pytest.raises(MultipartError):
        req._read_body_sync(_reader(body))
