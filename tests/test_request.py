import json
from datetime import datetime
from io import BytesIO

import pytest

from proper.errors import (
    ClientDisconnected,
    InvalidHeader,
    MultipartError,
    RequestEntityTooLarge,
    UriTooLong,
)
from proper.helpers import DotDict, MultiDict
from proper.request import Request, make_test_scope
from proper.request.formparser import (
    MultipartParser,
    MultipartPart,
    _safe_decode,
    copy_file,
    parse_json,
    parse_multipart_sync,
    parse_options_header,
    parse_query_string,
)
from proper.request.headers import parse_request_id
from proper.request.utils import make_test_scope as _make_test_scope


def _scope(url="/", method="GET", **kw):
    return make_test_scope(url, method=method, **kw)


def _req(url="/", method="GET", **kw):
    scope = _scope(url, method=method, **kw)
    return Request(scope)


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



class TestMakeTestScope:
    def test_defaults(self):
        scope = _make_test_scope()
        assert scope["type"] == "http"
        assert scope["method"] == "GET"
        assert scope["path"] == "/"
        assert scope["scheme"] == "http"
        assert scope["server"] == ("example.com", 80)
        assert scope["http_version"] == "1.1"

    def test_full_url(self):
        scope = _make_test_scope("http://myhost:9090/hello?x=1")
        assert scope["server"] == ("myhost", 9090)
        assert scope["path"] == "/hello"
        assert scope["query_string"] == b"x=1"

    def test_https_default_port(self):
        scope = _make_test_scope("https://secure.example.com/path")
        assert scope["scheme"] == "https"
        assert scope["server"] == ("secure.example.com", 443)

    def test_params_override_query(self):
        scope = _make_test_scope("/search?old=1", params={"q": "test"})
        assert scope["query_string"] == b"q=test"

    def test_custom_method(self):
        scope = _make_test_scope("/", method="post")
        assert scope["method"] == "POST"

    def test_custom_scope_type(self):
        scope = _make_test_scope("/", scope_type="websocket")
        assert scope["type"] == "websocket"

    def test_extra_kwargs(self):
        scope = _make_test_scope("/", client=("127.0.0.1", 12345))
        assert scope["client"] == ("127.0.0.1", 12345)

    def test_custom_headers(self):
        scope = _make_test_scope(
            "/",
            headers=[("x-custom", "value"), (b"x-binary", b"bval")],
        )
        header_names = [name for name, _ in scope["headers"]]
        assert b"x-custom" in header_names
        assert b"x-binary" in header_names

    def test_path_only_url(self):
        scope = _make_test_scope("/foo/bar")
        assert scope["path"] == "/foo/bar"
        assert scope["server"] == ("example.com", 80)


class TestRequestHeaders:
    def test_method_and_path(self):
        req = _req("/hello", method="POST")
        assert req.method == "POST"
        assert req.request_method == "POST"
        assert req.path == "/hello"

    def test_content_type(self):
        req = _req("/", headers=[("content-type", "application/json")])
        assert req.content_type == "application/json"

    def test_content_length(self):
        req = _req("/", headers=[("content-length", "42")])
        assert req.content_length == 42

    def test_content_length_zero(self):
        req = _req("/")
        assert req.content_length == 0

    def test_content_length_invalid(self):
        with pytest.raises(InvalidHeader, match="number"):
            _req("/", headers=[("content-length", "abc")])

    def test_content_length_negative(self):
        with pytest.raises(InvalidHeader, match="positive"):
            _req("/", headers=[("content-length", "-1")])

    def test_accept(self):
        req = _req("/", headers=[("accept", "text/html,application/json;q=0.5")])
        assert req.accept[0] == "text/html"
        assert req.accept[1] == "application/json"

    def test_accept_encoding(self):
        req = _req("/", headers=[("accept-encoding", "gzip,deflate;q=0.5")])
        assert req.accept_encoding[0] == "gzip"

    def test_accept_language(self):
        req = _req("/", headers=[("accept-language", "en-US,fr;q=0.5")])
        assert req.accept_language[0] == "en_US"

    def test_cookies(self):
        req = _req("/", headers=[("cookie", "a=1; b=2")])
        assert req.cookies["a"] == "1"
        assert req.cookies["b"] == "2"

    def test_cookies_multiple_headers(self):
        req = _req("/", headers=[("cookie", "a=1"), ("cookie", "b=2")])
        assert req.cookies["a"] == "1"
        assert req.cookies["b"] == "2"

    def test_cookie_alias(self):
        req = _req("/", headers=[("cookie", "a=1")])
        assert req.cookie == req.cookies

    def test_date_header(self):
        req = _req("/", headers=[("date", "Wed, 09 Jun 2021 10:18:14 GMT")])
        assert isinstance(req.date, datetime)

    def test_date_header_missing(self):
        req = _req("/")
        assert req.date is None

    def test_default_port_http(self):
        req = _req("http://example.com/")
        assert req.default_port == 80

    def test_default_port_https(self):
        req = _req("https://example.com/")
        assert req.default_port == 443

    def test_format_html(self):
        req = _req("/", headers=[("accept", "text/html")])
        assert req.format == "html"

    def test_format_json(self):
        req = _req("/", headers=[("accept", "application/json")])
        assert req.format == "json"

    def test_format_wildcard_default(self):
        req = _req("/", headers=[("accept", "*/*")])
        assert req.format == "html"

    def test_format_no_accept(self):
        req = _req("/")
        assert req.format == "html"

    def test_forwarded(self):
        req = _req("/", headers=[("forwarded", "for=192.0.2.60;proto=http;by=203.0.113.43")])
        assert req.forwarded[0]["for"] == "192.0.2.60"

    def test_host_with_port_default(self):
        req = _req("http://example.com/")
        assert req.host_with_port == "example.com"

    def test_host_with_port_non_default(self):
        req = _req("http://example.com:9090/")
        assert req.host_with_port == "example.com:9090"

    def test_if_none_match(self):
        req = _req("/", headers=[("if-none-match", '"etag1", "etag2"')])
        assert '"etag1"' in req.if_none_match
        assert '"etag2"' in req.if_none_match

    def test_if_modified_since(self):
        req = _req("/", headers=[("if-modified-since", "Wed, 09 Jun 2021 10:18:14 GMT")])
        assert isinstance(req.if_modified_since, datetime)

    def test_if_modified_since_missing(self):
        req = _req("/")
        assert req.if_modified_since is None

    def test_is_get(self):
        assert _req("/", method="GET").is_get is True
        assert _req("/", method="POST").is_get is False

    def test_is_head(self):
        assert _req("/", method="HEAD").is_head is True

    def test_is_post(self):
        assert _req("/", method="POST").is_post is True

    def test_is_put(self):
        assert _req("/", method="PUT").is_put is True

    def test_is_patch(self):
        assert _req("/", method="PATCH").is_patch is True

    def test_is_delete(self):
        assert _req("/", method="DELETE").is_delete is True

    def test_is_secure_http(self):
        req = _req("http://example.com/")
        assert req.is_secure is False

    def test_is_secure_https(self):
        req = _req("https://example.com/")
        assert req.is_secure is True

    def test_is_ssl_alias(self):
        req = _req("https://example.com/")
        assert req.is_ssl is True

    def test_is_xhr(self):
        req = _req("/", headers=[("x-requested-with", "XMLHttpRequest")])
        assert req.is_xhr is True

    def test_is_xhr_false(self):
        req = _req("/")
        assert req.is_xhr is False

    def test_port_is_default(self):
        assert _req("http://example.com/").port_is_default is True
        assert _req("http://example.com:9090/").port_is_default is False

    def test_port_string(self):
        assert _req("http://example.com/").port_string == ""
        assert _req("http://example.com:9090/").port_string == ":9090"

    def test_remote_ip_from_forwarded(self):
        req = _req("/", headers=[("forwarded", "for=1.2.3.4")])
        assert req.remote_ip == "1.2.3.4"

    def test_remote_ip_from_x_forwarded_for(self):
        req = _req("/", headers=[("x-forwarded-for", "5.6.7.8,proxy")])
        assert req.remote_ip == "5.6.7.8"

    def test_remote_ip_from_x_real_ip(self):
        req = _req("/", headers=[("x-real-ip", "9.10.11.12")])
        assert req.remote_ip == "9.10.11.12"

    def test_remote_ip_from_client(self):
        req = _req("/", client=("192.168.1.1", 5000))
        assert req.remote_ip == "192.168.1.1"

    def test_remote_ip_no_client(self):
        scope = _scope("/")
        scope.pop("client", None)
        req = Request(scope)
        assert req.remote_ip == ""

    def test_request_id(self):
        req = _req("/", headers=[("x-request-id", "req-123")])
        assert req.request_id == "req-123"

    def test_request_id_missing(self):
        req = _req("/")
        assert req.request_id is None

    def test_user_agent(self):
        req = _req("/", headers=[("user-agent", "TestBot/1.0")])
        assert req.user_agent == "TestBot/1.0"

    def test_user_agent_missing(self):
        req = _req("/")
        assert req.user_agent is None

    def test_protocol_from_x_forwarded_proto(self):
        req = _req("http://example.com/", headers=[("x-forwarded-proto", "https")])
        assert req.protocol == "https"
        assert req.is_secure is True

    def test_server_none_fallback_to_host_header(self):
        scope = _scope("/", headers=[("host", "example.com:8080")])
        scope["server"] = None
        req = Request(scope)
        assert req.host == "example.com"
        assert req.port == 8080

    def test_server_none_no_host_header(self):
        scope = _scope("/")
        scope["server"] = None
        # Remove the host header
        scope["headers"] = []
        req = Request(scope)
        assert req.host == ""

    def test_headers_get_bytes_header(self):
        scope = _scope("/")
        scope["headers"].append((b"x-test", b"\xe4\xb8\xad"))
        req = Request(scope)
        val = req.headers.get("x-test")
        assert val is not None

    def test_headers_get_missing(self):
        req = _req("/")
        assert req.headers.get("nonexistent") is None

    def test_headers_get_string(self):
        scope = _scope("/")
        # Inject a string value directly instead of bytes
        req = Request(scope)
        req.headers["x-str"] = "string-value"
        assert req.headers.get("x-str") == "string-value"

    # --- accept edge cases ---

    def test_accept_empty(self):
        req = _req("/")
        assert req.accept == []

    def test_accept_quality_sorting(self):
        req = _req("/", headers=[
            ("accept", "text/plain;q=0.5,text/html;q=0.9,application/json;q=0.1"),
        ])
        assert req.accept == ["text/html", "text/plain", "application/json"]

    def test_accept_default_quality_is_1(self):
        req = _req("/", headers=[("accept", "text/html,text/plain;q=0.5")])
        assert req.accept == ["text/html", "text/plain"]

    def test_accept_encoding_empty(self):
        req = _req("/")
        assert req.accept_encoding == []

    def test_accept_language_empty(self):
        req = _req("/")
        assert req.accept_language == []

    def test_accept_with_quoted_params(self):
        """Exercise the parse_multivalue slow path (quoted strings)."""
        req = _req("/", headers=[
            ("accept", 'text/html;level="1",application/json;q=0.5'),
        ])
        assert req.accept[0] == "text/html"
        assert req.accept[1] == "application/json"

    def test_accept_with_escaped_quotes(self):
        """Quoted string with escaped quote inside."""
        req = _req("/", headers=[
            ("accept", r'text/html;level="foo\"bar",text/plain;q=0.5'),
        ])
        assert req.accept[0] == "text/html"
        assert req.accept[1] == "text/plain"

    def test_accept_semicolon_without_equals(self):
        """Semicolon-separated attribute without =value (slow path)."""
        req = _req("/", headers=[
            ("accept", '"text/html";level'),
        ])
        # Should still parse without error
        assert len(req.accept) >= 1

    # --- if_none_match edge cases ---

    def test_if_none_match_empty(self):
        req = _req("/")
        assert req.if_none_match == []

    def test_if_none_match_single(self):
        req = _req("/", headers=[("if-none-match", '"etag1"')])
        assert req.if_none_match == ['"etag1"']

    def test_if_none_match_whitespace(self):
        req = _req("/", headers=[("if-none-match", '"a", "b"')])
        assert '"a"' in req.if_none_match
        assert '"b"' in req.if_none_match

    # --- cookie edge cases ---

    def test_cookies_empty_header(self):
        req = _req("/")
        assert req.cookies == {}

    def test_cookies_empty_name(self):
        """Cookie chunk without '=' gets empty name."""
        req = _req("/", headers=[("cookie", "justvalue")])
        assert req.cookies[""] == "justvalue"

    def test_cookies_quoted_value(self):
        req = _req("/", headers=[("cookie", 'a="quoted"')])
        assert req.cookies["a"] == "quoted"

    def test_cookies_empty_pair_skipped(self):
        req = _req("/", headers=[("cookie", "a=1;  ;b=2")])
        assert req.cookies["a"] == "1"
        assert req.cookies["b"] == "2"

    # --- host parsing via header fallback ---

    def test_host_from_header_ipv6(self):
        scope = _scope("/", headers=[("host", "[::1]")])
        scope["server"] = None
        req = Request(scope)
        assert req.host == "::1"
        assert req.port == 80  # default

    def test_host_from_header_ipv6_with_port(self):
        scope = _scope("/", headers=[("host", "[::1]:9090")])
        scope["server"] = None
        req = Request(scope)
        assert req.host == "::1"
        assert req.port == 9090

    def test_host_from_header_non_decimal_port(self):
        scope = _scope("/", headers=[("host", "example.com:abc")])
        scope["server"] = None
        req = Request(scope)
        assert req.host == "example.com"
        assert req.port == 80  # non-decimal port → 0, then default_port

    def test_host_from_header_simple(self):
        scope = _scope("/", headers=[("host", "myhost:8080")])
        scope["server"] = None
        req = Request(scope)
        assert req.host == "myhost"
        assert req.port == 8080

    # --- request_id edge cases ---

    def test_request_id_truncated(self):
        long_id = "a" * 300
        req = _req("/", headers=[("x-request-id", long_id)])
        assert len(req.request_id) == 200

    def test_request_id_non_ascii_removed(self):
        req = _req("/", headers=[("x-request-id", "abc\x80\x81def")])
        assert req.request_id == "abcdef"

    # --- forwarded edge cases ---

    def test_forwarded_empty(self):
        req = _req("/")
        assert req.forwarded == []

    def test_forwarded_multiple_proxies(self):
        req = _req("/", headers=[
            ("forwarded", "for=1.2.3.4,for=5.6.7.8"),
        ])
        assert len(req.forwarded) == 2
        assert req.forwarded[0]["for"] == "1.2.3.4"
        assert req.forwarded[1]["for"] == "5.6.7.8"

    def test_forwarded_quoted_values(self):
        req = _req("/", headers=[
            ("forwarded", 'for="1.2.3.4"'),
        ])
        assert req.forwarded[0]["for"] == "1.2.3.4"

    def test_forwarded_escaped_quotes(self):
        req = _req("/", headers=[
            ("forwarded", r'for="val\"ue"'),
        ])
        assert req.forwarded[0]["for"] == 'val"ue'

    def test_forwarded_port_suffix(self):
        req = _req("/", headers=[
            ("forwarded", "for=1.2.3.4:8080"),
        ])
        assert req.forwarded[0]["for"] == "1.2.3.4:8080"

    def test_forwarded_multiple_params(self):
        req = _req("/", headers=[
            ("forwarded", "for=1.2.3.4;proto=https;by=proxy"),
        ])
        fwd = req.forwarded[0]
        assert fwd["for"] == "1.2.3.4"
        assert fwd["proto"] == "https"
        assert fwd["by"] == "proxy"

    def test_forwarded_case_insensitive_keys(self):
        req = _req("/", headers=[
            ("forwarded", "For=1.2.3.4;Proto=https"),
        ])
        fwd = req.forwarded[0]
        assert fwd["for"] == "1.2.3.4"
        assert fwd["proto"] == "https"

    def test_forwarded_whitespace_between_pairs(self):
        req = _req("/", headers=[
            ("forwarded", "for=1.2.3.4 ; proto=https"),
        ])
        fwd = req.forwarded[0]
        assert fwd["for"] == "1.2.3.4"
        assert fwd["proto"] == "https"

    def test_forwarded_bad_syntax_skipped(self):
        req = _req("/", headers=[
            ("forwarded", "!!!,for=1.2.3.4"),
        ])
        # First proxy is empty (bad syntax skipped), second has the value
        assert req.forwarded[1]["for"] == "1.2.3.4"

    def test_forwarded_bad_syntax_after_valid(self):
        """Two valid pairs without separator → bad syntax, skip to next comma."""
        req = _req("/", headers=[
            ("forwarded", "for=1.2.3.4 for=bad,for=5.6.7.8"),
        ])
        # After first valid pair, "for=bad" is encountered without separator
        # so it skips to comma, then parses for=5.6.7.8
        assert req.forwarded[0]["for"] == "1.2.3.4"
        assert req.forwarded[1]["for"] == "5.6.7.8"


class TestRequest:
    def test_repr(self):
        req = _req("/hello", method="GET")
        r = repr(req)
        assert "GET" in r
        assert "/hello" in r

    def test_app(self, app):
        scope = _scope("/")
        scope["app"] = app
        req = Request(scope)
        assert req.app is app

    def test_session_default(self):
        req = _req("/")
        assert isinstance(req.session, DotDict)
        assert len(req.session) == 0

    def test_session_setter(self):
        req = _req("/")
        req.session = {"key": "val"}
        assert isinstance(req.session, DotDict)
        assert req.session.key == "val"

    def test_http_version(self):
        req = _req("/")
        assert req.http_version == "1.1"

    def test_flashes_empty(self):
        req = _req("/")
        assert req.flashes == []

    def test_flashes_from_session(self):
        req = _req("/")
        req.session = {"_flashes": [("info", "hello")]}
        assert req.flashes == [("info", "hello")]

    def test_query(self, app):
        scope = _scope("http://example.com/search?q=test&page=2")
        scope["app"] = app
        req = Request(scope)
        assert req.query.get("q") == "test"
        assert req.query.get("page") == "2"

    def test_query_cached(self, app):
        scope = _scope("http://example.com/?x=1")
        scope["app"] = app
        req = Request(scope)
        q1 = req.query
        q2 = req.query
        assert q1 is q2

    def test_query_string(self):
        req = _req("http://example.com/path?a=1&b=2")
        assert req.query_string == "a=1&b=2"

    def test_query_string_bytes(self):
        scope = _scope("/")
        scope["query_string"] = b"key=val"
        req = Request(scope)
        assert req.query_string == "key=val"

    def test_query_string_str(self):
        scope = _scope("/")
        scope["query_string"] = "key=val"
        req = Request(scope)
        assert req.query_string == "key=val"

    def test_query_string_empty(self):
        req = _req("/")
        assert req.query_string == ""

    def test_url(self):
        req = _req("http://example.com/path?q=1")
        assert req.url == "/path?q=1"

    def test_get_url_without_query(self):
        req = _req("http://example.com/path?q=1")
        assert req.get_url(include_query=False) == "/path"

    def test_get_url_no_query_string(self):
        req = _req("http://example.com/path")
        assert req.get_url() == "/path"

    def test_form_default(self):
        req = _req("/")
        assert isinstance(req.form, MultiDict)
        assert len(req.form) == 0

    def test_matched_defaults(self):
        req = _req("/")
        assert not req.matched_route
        assert not req.matched_params
        assert not req.matched_action

    def test_get_cookie(self):
        req = _req("/", headers=[("cookie", "name=Jon")])
        assert req.get_cookie("name") == "Jon"

    def test_get_cookie_default(self):
        req = _req("/")
        assert req.get_cookie("missing") is None
        assert req.get_cookie("missing", "fallback") == "fallback"

    def test_get_signed_cookie(self, app):
        signed_value = app.dumps("secret_data", "cookie")
        scope = _scope("/")
        scope["app"] = app
        scope["headers"].append((b"cookie", f"test={signed_value}".encode()))
        req = Request(scope)
        assert req.get_signed_cookie("test") == "secret_data"

    def test_get_signed_cookie_missing(self, app):
        scope = _scope("/")
        scope["app"] = app
        req = Request(scope)
        assert req.get_signed_cookie("missing") is None
        assert req.get_signed_cookie("missing", "default") == "default"

    def test_get_signed_cookie_bad_signature(self, app):
        scope = _scope("/")
        scope["app"] = app
        scope["headers"].append((b"cookie", b"test=tampered_value"))
        req = Request(scope)
        assert req.get_signed_cookie("test") is None
        assert req.get_signed_cookie("test", "fallback") == "fallback"

    def test_get_signed_cookie_bytes_value(self, app):
        from unittest.mock import patch

        signed_value = app.dumps("bytes_test")
        scope = _scope("/")
        scope["app"] = app
        scope["headers"].append((b"cookie", f"test={signed_value}".encode()))
        req = Request(scope)
        # Patch loads to return bytes
        with patch.object(
            type(app), "loads", return_value=b"decoded_bytes"
        ):
            result = req.get_signed_cookie("test")
            assert result == "decoded_bytes"


class TestRequestAsync:
    async def test_get_body(self, app):
        body = b"hello world"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/json"),
        ])
        scope["app"] = app
        req = Request(scope)
        receive = _make_receive(body)
        result = await req._get_body(receive)
        assert result == body

    async def test_get_body_chunked(self, app):
        body = b"hello world"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/json"),
        ])
        scope["app"] = app
        req = Request(scope)
        receive = _make_receive(body, chunk_size=3)
        result = await req._get_body(receive)
        assert result == body

    async def test_get_stream_max_content_length(self, app):
        app.config.MAX_CONTENT_LENGTH = 5
        body = b"toolongbody"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/json"),
        ])
        scope["app"] = app
        req = Request(scope)
        receive = _make_receive(body)
        with pytest.raises(RequestEntityTooLarge):
            await req._get_body(receive)
        app.config.MAX_CONTENT_LENGTH = 0

    async def test_get_stream_disconnect(self, app):
        scope = _scope("/", method="POST", headers=[
            ("content-length", "10"),
            ("content-type", "application/json"),
        ])
        scope["app"] = app
        req = Request(scope)
        receive = _make_disconnect_receive()
        with pytest.raises(ClientDisconnected):
            await req._get_body(receive)

    async def test_parse_body_get_skips(self, app):
        scope = _scope("/", method="GET")
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(b""))
        assert len(req.form) == 0

    async def test_parse_body_head_skips(self, app):
        scope = _scope("/", method="HEAD")
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(b""))
        assert len(req.form) == 0

    async def test_parse_body_no_content_length_skips(self, app):
        scope = _scope("/", method="POST")
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(b""))
        assert len(req.form) == 0

    async def test_parse_body_json(self, app):
        body = json.dumps({"key": "value"}).encode()
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/json"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.form.get("key") == "value"

    async def test_parse_body_json_charset(self, app):
        body = json.dumps({"x": "y"}).encode()
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/json; charset=utf-8"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.form.get("x") == "y"

    async def test_parse_body_form_urlencoded(self, app):
        body = b"name=Jon&age=30"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/x-www-form-urlencoded"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.form.get("name") == "Jon"
        assert req.form.get("age") == "30"

    async def test_parse_body_form_x_url_encoded(self, app):
        body = b"key=val"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/x-url-encoded"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.form.get("key") == "val"

    async def test_parse_body_multipart(self, app):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": "field1", "value": "hello"}],
            boundary=boundary,
        )
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", f"multipart/form-data; boundary={boundary}"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.form.get("field1") == "hello"

    async def test_parse_body_unparsed_content_type_exposes_raw_body(self, app):
        """Binary or unparsed content types don't fail - the controller
        can still reach the bytes via `request.body`."""
        body = b"<root/>"
        scope = _scope("/", method="POST", headers=[
            ("content-length", str(len(body))),
            ("content-type", "application/xml"),
        ])
        scope["app"] = app
        req = Request(scope)
        await req._parse_body(_make_receive(body))
        assert req.body == body
        assert len(req.form) == 0


class TestParseOptionsHeader:
    def test_empty(self):
        ct, opts = parse_options_header("")
        assert ct == ""
        assert opts == {}

    def test_simple(self):
        ct, opts = parse_options_header("text/html")
        assert ct == "text/html"

    def test_with_params(self):
        ct, opts = parse_options_header("text/html; charset=utf-8")
        assert ct == "text/html"
        assert opts["charset"] == "utf-8"

    def test_multipart_boundary(self):
        ct, opts = parse_options_header(
            "multipart/form-data; boundary=----WebKitFormBoundary"
        )
        assert ct == "multipart/form-data"
        assert opts["boundary"] == "----WebKitFormBoundary"

    def test_existing_options_dict(self):
        existing = {"extra": "value"}
        ct, opts = parse_options_header("text/plain", options=existing)
        assert opts["extra"] == "value"
        assert opts is existing


class TestParseQueryString:
    def test_simple(self):
        result = parse_query_string("a=1&b=2")
        assert result.get("a") == "1"
        assert result.get("b") == "2"

    def test_empty(self):
        result = parse_query_string("")
        assert len(result) == 0

    def test_blank_values(self):
        result = parse_query_string("key=")
        assert result.get("key") == ""

    def test_max_query_size(self):
        with pytest.raises(UriTooLong):
            parse_query_string("x" * 100, max_query_size=10)

    def test_encoding(self):
        result = parse_query_string("name=%C3%A9", encoding="utf-8")
        assert result.get("name") == "\u00e9"


class TestParseJson:
    def test_valid(self):
        result = parse_json('{"key": "value"}')
        assert result.get("key") == "value"

    def test_invalid_strict(self):
        with pytest.raises(MultipartError):
            parse_json("not json")

    def test_invalid_non_strict(self):
        result = parse_json("not json", strict=False)
        assert len(result) == 0


class TestCopyFile:
    def test_basic(self):
        src = BytesIO(b"hello world")
        dst = BytesIO()
        size = copy_file(src, dst)
        assert size == 11
        assert dst.getvalue() == b"hello world"

    def test_maxread(self):
        src = BytesIO(b"hello world")
        dst = BytesIO()
        size = copy_file(src, dst, maxread=5)
        assert size == 5
        assert dst.getvalue() == b"hello"

    def test_empty(self):
        src = BytesIO(b"")
        dst = BytesIO()
        size = copy_file(src, dst)
        assert size == 0


class TestSafeDecode:
    def test_utf8(self):
        assert _safe_decode(b"hello", "utf-8") == "hello"

    def test_latin1_fallback(self):
        raw = b"\xe9"
        result = _safe_decode(raw, "utf-8")
        assert result == raw.decode("latin-1")

    def test_bad_codec_fallback(self):
        result = _safe_decode(b"hello", "nonexistent-codec")
        assert result == "hello"


class TestParseRequestId:
    def test_none_returns_none(self):
        assert parse_request_id(None) is None

    def test_simple_id(self):
        assert parse_request_id("abc-123") == "abc-123"

    def test_hyphens_preserved(self):
        """Regression: hyphens must not be stripped as non-ASCII."""
        rid = "req-abc-def-123"
        assert parse_request_id(rid) == rid

    def test_non_ascii_stripped(self):
        assert parse_request_id("abc\u00e9def") == "abcdef"

    def test_truncated_to_max_length(self):
        long_id = "x" * 300
        result = parse_request_id(long_id)
        assert len(result) == 200


class TestMultipartPart:
    def test_defaults(self):
        part = MultipartPart()
        assert part.name == ""
        assert part.filename is None
        assert part.file is None
        assert part.content_type is None
        assert part.size == 0
        assert part.headers == []

    def test_is_buffered_bytesio(self):
        part = MultipartPart()
        part.file = BytesIO(b"data")
        assert part.is_buffered() is True

    def test_is_buffered_other(self):
        part = MultipartPart()
        from tempfile import SpooledTemporaryFile
        part.file = SpooledTemporaryFile()
        assert part.is_buffered() is False
        part.close()

    def test_value_and_raw(self):
        part = MultipartPart()
        part.file = BytesIO(b"hello")
        assert part.raw == b"hello"
        assert part.value == "hello"
        # file position should be restored
        assert part.file.tell() == 0

    def test_raw_no_file(self):
        part = MultipartPart()
        assert part.raw == b""

    def test_save_as(self, tmp_path):
        part = MultipartPart()
        part.file = BytesIO(b"file content")
        dest = tmp_path / "output.bin"
        size = part.save_as(str(dest))
        assert size == 12
        assert dest.read_bytes() == b"file content"
        # file position should be restored
        assert part.file.tell() == 0

    def test_close(self):
        part = MultipartPart()
        part.file = BytesIO(b"data")
        part.close()
        assert part.file is None

    def test_close_no_file(self):
        part = MultipartPart()
        part.close()  # should not raise


class TestMultipartParser:
    def test_single_field(self):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": "field1", "value": "hello"}],
            boundary=boundary,
        )
        parser = MultipartParser(boundary)
        items = parser.parse_sync(body)
        assert len(items) == 1
        assert items[0] == ("field1", "hello")

    def test_multiple_fields(self):
        boundary = "testboundary"
        body = _build_multipart(
            [
                {"name": "a", "value": "1"},
                {"name": "b", "value": "2"},
            ],
            boundary=boundary,
        )
        parser = MultipartParser(boundary)
        items = parser.parse_sync(body)
        assert len(items) == 2

    def test_file_upload(self):
        boundary = "testboundary"
        body = _build_multipart(
            [
                {
                    "name": "file",
                    "value": b"file content here",
                    "filename": "test.txt",
                    "content_type": "text/plain",
                },
            ],
            boundary=boundary,
        )
        parser = MultipartParser(boundary)
        items = parser.parse_sync(body)
        assert len(items) == 1
        name, part = items[0]
        assert name == "file"
        assert isinstance(part, MultipartPart)
        assert part.filename == "test.txt"
        assert part.content_type == "text/plain"
        assert part.raw == b"file content here"
        part.close()

    def test_mixed_fields_and_files(self):
        boundary = "testboundary"
        body = _build_multipart(
            [
                {"name": "title", "value": "My File"},
                {
                    "name": "upload",
                    "value": b"binary data",
                    "filename": "data.bin",
                    "content_type": "application/octet-stream",
                },
            ],
            boundary=boundary,
        )
        parser = MultipartParser(boundary)
        items = parser.parse_sync(body)
        assert items[0] == ("title", "My File")
        name, part = items[1]
        assert isinstance(part, MultipartPart)
        part.close()

    def test_no_boundary_error(self):
        with pytest.raises(MultipartError, match="boundary"):
            parse_multipart_sync(b"", {})

    def test_max_fields_exceeded(self):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": f"field{i}", "value": "v"} for i in range(5)],
            boundary=boundary,
        )
        parser = MultipartParser(boundary, max_fields=2)
        with pytest.raises(MultipartError, match="Too many fields"):
            parser.parse_sync(body)

    def test_max_files_exceeded(self):
        boundary = "testboundary"
        body = _build_multipart(
            [
                {"name": f"f{i}", "value": b"data", "filename": f"f{i}.txt"}
                for i in range(5)
            ],
            boundary=boundary,
        )
        parser = MultipartParser(boundary, max_files=2)
        with pytest.raises(MultipartError, match="Too many files"):
            parser.parse_sync(body)

    def test_max_part_size_exceeded(self):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": "big", "value": "x" * 100}],
            boundary=boundary,
        )
        parser = MultipartParser(boundary, max_part_size=10)
        with pytest.raises(MultipartError, match="exceeded"):
            parser.parse_sync(body)

    def test_missing_content_disposition(self):
        boundary = "testboundary"
        # Manually craft a body without Content-Disposition
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: text/plain\r\n"
            f"\r\n"
            f"value\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        parser = MultipartParser(boundary)
        with pytest.raises(MultipartError, match="Content-Disposition"):
            parser.parse_sync(body)

    def test_missing_name_in_disposition(self):
        boundary = "testboundary"
        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data\r\n"
            f"\r\n"
            f"value\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        parser = MultipartParser(boundary)
        with pytest.raises(MultipartError, match="name"):
            parser.parse_sync(body)

    def test_parse_multipart_sync_function(self):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": "x", "value": "y"}],
            boundary=boundary,
        )
        result = parse_multipart_sync(body, {"boundary": boundary})
        assert isinstance(result, MultiDict)
        assert result.get("x") == "y"

    def test_chunked_parse(self):
        boundary = "testboundary"
        body = _build_multipart(
            [{"name": "field", "value": "hello"}],
            boundary=boundary,
        )
        parser = MultipartParser(boundary)
        items = parser.parse_sync(body)
        assert items[0] == ("field", "hello")

    def test_file_parts_closed_on_error(self):
        boundary = "testboundary"
        # Create body with a file upload then exceed max_fields with non-file
        parts = [
            {"name": "f", "value": b"data", "filename": "f.txt"},
        ]
        parts.extend(
            {"name": f"field{i}", "value": "v"} for i in range(5)
        )
        body = _build_multipart(parts, boundary=boundary)
        parser = MultipartParser(boundary, max_fields=2)
        with pytest.raises(MultipartError):
            parser.parse_sync(body)
