import json

import pytest

from proper.errors import ClientDisconnected, RequestEntityTooLarge
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
    """Stand-in for the server's body reader."""
    async def read():
        return body

    return read


def _post(app, body: bytes, content_type="application/json", method="POST"):
    return make_test_request("/", method=method, app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", content_type),
    ])


async def test_read_body(app):
    body = b'{"a": 1}'
    req = _post(app, body)
    await req._read_body(_reader(body))
    assert req.body == body
    assert req.form["a"] == 1


async def test_read_body_over_max_content_length_is_refused_before_reading(app):
    app.config.MAX_CONTENT_LENGTH = 5
    body = b"toolongbody"
    req = _post(app, body)
    reads = []

    async def read():
        reads.append(True)
        return body

    with pytest.raises(RequestEntityTooLarge):
        await req._read_body(read)
    assert reads == []
    app.config.MAX_CONTENT_LENGTH = 0


async def test_read_body_error_propagates(app):
    req = _post(app, b"0123456789")

    async def read():
        raise ClientDisconnected()

    with pytest.raises(ClientDisconnected):
        await req._read_body(read)


async def test_parse_body_get_skips(app):
    req = make_test_request("/", method="GET", app=app)
    await req._read_body(_reader(b""))
    assert len(req.form) == 0

async def test_parse_body_head_skips(app):
    req = make_test_request("/", method="HEAD", app=app)
    await req._read_body(_reader(b""))
    assert len(req.form) == 0

async def test_parse_body_no_content_length_skips(app):
    req = make_test_request("/", method="POST", app=app)
    await req._read_body(_reader(b""))
    assert len(req.form) == 0

async def test_parse_body_json(app):
    body = json.dumps({"key": "value"}).encode()
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    await req._read_body(_reader(body))
    assert req.form.get("key") == "value"

async def test_parse_body_json_charset(app):
    body = json.dumps({"x": "y"}).encode()
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json; charset=utf-8"),
    ])
    await req._read_body(_reader(body))
    assert req.form.get("x") == "y"

async def test_parse_body_form_urlencoded(app):
    body = b"name=Jon&age=30"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-www-form-urlencoded"),
    ])
    await req._read_body(_reader(body))
    assert req.form.get("name") == "Jon"
    assert req.form.get("age") == "30"

async def test_parse_body_form_x_url_encoded(app):
    body = b"key=val"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-url-encoded"),
    ])
    await req._read_body(_reader(body))
    assert req.form.get("key") == "val"

async def test_parse_body_multipart(app):
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "field1", "value": "hello"}],
        boundary=boundary,
    )
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", f"multipart/form-data; boundary={boundary}"),
    ])
    await req._read_body(_reader(body))
    assert req.form.get("field1") == "hello"

async def test_parse_body_unparsed_content_type_exposes_raw_body(app):
    """Binary or unparsed content types don't fail - the controller
    can still reach the bytes via `request.body`."""
    body = b"<root/>"
    req = make_test_request("/", method="POST", app=app, headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/xml"),
    ])
    await req._read_body(_reader(body))
    assert req.body == body
    assert len(req.form) == 0
