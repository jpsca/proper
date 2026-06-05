import json

import pytest

from proper.core.request import Request
from proper.errors import ClientDisconnected, RequestEntityTooLarge
from proper.helpers.asgi import make_test_scope


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


def _make_receive(body: bytes, *, chunk_size: int = 0):
    """Create an ASGI receive callable that yields body in chunks."""
    if chunk_size <= 0:
        chunks = [body]
    else:
        chunks = [body[i:i + chunk_size] for i in range(0, len(body), chunk_size)]

    idx = 0

    async def receive():
        nonlocal idx
        if idx < len(chunks):
            chunk = chunks[idx]
            idx += 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": idx < len(chunks),
            }
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


def _make_disconnect_receive():
    async def receive():
        return {"type": "http.disconnect"}

    return receive


async def test_get_body(app):
    body = b"hello world"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    scope["app"] = app
    req = Request(scope)
    receive = _make_receive(body)
    result = await req._get_body(receive)
    assert result == body

async def test_get_body_chunked(app):
    body = b"hello world"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    scope["app"] = app
    req = Request(scope)
    receive = _make_receive(body, chunk_size=3)
    result = await req._get_body(receive)
    assert result == body

async def test_get_stream_max_content_length(app):
    app.config.MAX_CONTENT_LENGTH = 5
    body = b"toolongbody"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    scope["app"] = app
    req = Request(scope)
    receive = _make_receive(body)
    with pytest.raises(RequestEntityTooLarge):
        await req._get_body(receive)
    app.config.MAX_CONTENT_LENGTH = 0

async def test_get_stream_disconnect(app):
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", "10"),
        ("content-type", "application/json"),
    ])
    scope["app"] = app
    req = Request(scope)
    receive = _make_disconnect_receive()
    with pytest.raises(ClientDisconnected):
        await req._get_body(receive)

async def test_parse_body_get_skips(app):
    scope = make_test_scope("/", method="GET")
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(b""))
    assert len(req.form) == 0

async def test_parse_body_head_skips(app):
    scope = make_test_scope("/", method="HEAD")
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(b""))
    assert len(req.form) == 0

async def test_parse_body_no_content_length_skips(app):
    scope = make_test_scope("/", method="POST")
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(b""))
    assert len(req.form) == 0

async def test_parse_body_json(app):
    body = json.dumps({"key": "value"}).encode()
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.form.get("key") == "value"

async def test_parse_body_json_charset(app):
    body = json.dumps({"x": "y"}).encode()
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/json; charset=utf-8"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.form.get("x") == "y"

async def test_parse_body_form_urlencoded(app):
    body = b"name=Jon&age=30"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-www-form-urlencoded"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.form.get("name") == "Jon"
    assert req.form.get("age") == "30"

async def test_parse_body_form_x_url_encoded(app):
    body = b"key=val"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/x-url-encoded"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.form.get("key") == "val"

async def test_parse_body_multipart(app):
    boundary = "testboundary"
    body = _build_multipart(
        [{"name": "field1", "value": "hello"}],
        boundary=boundary,
    )
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", f"multipart/form-data; boundary={boundary}"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.form.get("field1") == "hello"

async def test_parse_body_unparsed_content_type_exposes_raw_body(app):
    """Binary or unparsed content types don't fail - the controller
    can still reach the bytes via `request.body`."""
    body = b"<root/>"
    scope = make_test_scope("/", method="POST", headers=[
        ("content-length", str(len(body))),
        ("content-type", "application/xml"),
    ])
    scope["app"] = app
    req = Request(scope)
    await req._parse_body(_make_receive(body))
    assert req.body == body
    assert len(req.form) == 0
