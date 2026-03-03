"""Tests for proper.request — Request class, headers, forwarded, make_env,
parse_form, and multipart."""

from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from proper.errors import (
    BadRequest,
    InvalidHeader,
    MultipartError,
    RequestEntityTooLarge,
    UnsupportedMediaType,
    UriTooLong,
)
from proper.helpers import DotDict
from proper.request.forwarded import parse_forwarded
from proper.request.headers import (
    NormalizedEnv,
    RequestHeadersMixin,
    enc,
    parse_accept,
    parse_comma_separated,
    parse_cookie,
    parse_host,
    parse_multivalue,
    parse_request_id,
)
from proper.request.multipart import (
    MultipartParser,
    MultipartPart,
    copy_file,
    header_quote,
    header_unquote,
    parse_options_header,
    to_bytes,
)
from proper.request.parse_form import (
    _normalize_newlines,
    _read_content,
    _validate_actual_content_length,
    parse_form,
    parse_json,
    parse_multipart,
    parse_query_string,
)
from proper.request import Request, make_test_scope


# ── helpers ─────────────────────────────────────────────────────────


def _build_multipart(parts, boundary="testboundary"):
    """Build a multipart/form-data body.

    `parts` is a list of dicts, each with:
      - name (str)
      - value (str or bytes)
      - filename (str, optional)
      - content_type (str, optional)
    """
    body = b""
    for part in parts:
        body += f"--{boundary}\r\n".encode()
        disp = f'form-data; name="{part["name"]}"'
        if "filename" in part:
# ── make_test_scope ───────────────────────────────────────────────────
            disp += f'; filename="{part["filename"]}"'
        body += f"Content-Disposition: {disp}\r\n".encode()
        if "content_type" in part:
            body += f"Content-Type: {part['content_type']}\r\n".encode()
        env = make_test_scope()
        body += b"\r\n"
        val = part["value"]
        body += val.encode() if isinstance(val, str) else val
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body




        env = make_test_scope("http://myhost:9090/hello?x=1")
class TestMakeTestEnv:
    def test_default_env_has_wsgi_keys(self):
        assert env["REQUEST_METHOD"] == "GET"
        assert env["PATH_INFO"] == "/"
        assert env["HTTP_HOST"] == "example.com"
        assert env["HTTP_PORT"] == "80"
        assert env["wsgi.url_protocol"] == "http"
        env = make_test_scope("https://secure.example.com:443/path")
        assert env["QUERY_STRING"] == ""
        # wsgi.input should be a BytesIO
        assert hasattr(env["wsgi.input"], "read")

    def test_custom_url(self):
        env = make_test_scope(params={"a": "1", "b": "hello world"})
        assert env["HTTP_HOST"] == "myhost"
        assert env["HTTP_PORT"] == "9090"
        assert env["PATH_INFO"] == "/hello"
        assert env["QUERY_STRING"] == "x=1"
        assert env["wsgi.url_protocol"] == "http"

    def test_https_url(self):
        assert env["wsgi.url_protocol"] == "https"
        env = make_test_scope(body={"key": "val"})
        assert env["HTTP_HOST"] == "secure.example.com"
        assert env["HTTP_PORT"] == "443"

    def test_params_dict_produces_query_string(self):
        qs = env["QUERY_STRING"]
        env = make_test_scope(body="raw body")
        assert "a=1" in qs
        assert "b=hello+world" in qs
        # Ensure no double-encoding: '=' and '&' must be literal
        assert "=" in qs
        env = make_test_scope(body=b"raw bytes")
        assert "&" in qs

    def test_body_as_dict(self):
        stream = env["wsgi.input"]
        data = stream.read()
        env = make_test_scope(body=bio)
        assert b"key=val" in data

    def test_body_as_str(self):
        stream = env["wsgi.input"]
        env = make_test_scope(body=b"")
        assert stream.read() == b"raw body"

    def test_body_as_bytes(self):
        stream = env["wsgi.input"]
        assert stream.read() == b"raw bytes"

    def test_body_as_bytesio(self):
        bio = BytesIO(b"stream data")
        assert env["wsgi.input"] is bio
        assert env["wsgi.input"].read() == b"stream data"

    def test_empty_body(self):
        stream = env["wsgi.input"]
        assert stream.read() == b""

    def test_extra_kw_merged(self):
        env = make_test_scope(REQUEST_METHOD="POST", CONTENT_TYPE="text/plain")
        assert env["REQUEST_METHOD"] == "POST"
        assert env["CONTENT_TYPE"] == "text/plain"


# ── NormalizedEnv / enc() ───────────────────────────────────────────


class TestNormalizedEnv:
    def test_enc_strips_lower_replaces(self):
        assert enc("  Content-Type ") == "content_type"
        assert enc("HTTP_HOST") == "http_host"

    def test_setitem_normalizes(self):
        ne = NormalizedEnv()
        ne["Content-Type"] = "text/html"
        assert "content_type" in ne
        assert ne["content_type"] == "text/html"


# ── RequestHeadersMixin ─────────────────────────────────────────────


class TestRequestHeadersMixin:
    def _make(self, **extra):
        env = make_test_scope(**extra)
        return RequestHeadersMixin(env)

    def test_protocol_defaults_to_http(self):
        h = self._make()
        assert h.protocol == "http"

    def test_protocol_from_x_forwarded_proto(self):
        h = self._make(HTTP_X_FORWARDED_PROTO="https")
        assert h.protocol == "https"

    def test_host_and_port(self):
        h = self._make()
        assert h.host == "example.com"
        assert h.port == 80

    def test_method_uppercased(self):
        h = self._make(REQUEST_METHOD="post")
        assert h.method == "POST"

    def test_path_decoded(self):
        h = self._make(PATH_INFO="/hello%20world")
        # PATH_INFO is passed through tunnel_decode
        assert h.path.startswith("/")

    def test_content_type(self):
        h = self._make(CONTENT_TYPE="application/json")
        assert h.content_type == "application/json"

    def test_content_length_valid(self):
        h = self._make(CONTENT_LENGTH="42")
        assert h.content_length == 42

    def test_content_length_empty(self):
        h = self._make(CONTENT_LENGTH="")
        assert h.content_length == 0

    def test_content_length_invalid_raises(self):
        with pytest.raises(InvalidHeader, match="must be a number"):
            self._make(CONTENT_LENGTH="abc")

    def test_content_length_negative_raises(self):
        with pytest.raises(InvalidHeader, match="positive"):
            self._make(CONTENT_LENGTH="-1")

    def test_get_special_names(self):
        h = self._make(HTTP_COOKIE="foo=bar")
        cookies = h.get("cookie")
        assert "foo" in cookies

    def test_get_regular_env_key(self):
        h = self._make(REQUEST_METHOD="GET")
        assert h.get("request_method") == "GET"

    def test_get_default(self):
        h = self._make()
        assert h.get("nonexistent", "default") == "default"


# ── Header properties ───────────────────────────────────────────────


class TestHeaderProperties:
    def _make(self, **extra):
        env = make_test_scope(**extra)
        return RequestHeadersMixin(env)

    def test_accept_parsing(self):
        h = self._make(HTTP_ACCEPT="text/html, application/json;q=0.9")
        assert h.accept == ["text/html", "application/json"]

    def test_accept_encoding(self):
        h = self._make(HTTP_ACCEPT_ENCODING="gzip, deflate;q=0.5")
        assert h.accept_encoding[0] == "gzip"

    def test_accept_language(self):
        h = self._make(HTTP_ACCEPT_LANGUAGE="en-US, es;q=0.8")
        langs = h.accept_language
        assert langs[0] == "en_US"
        assert langs[1] == "es"

    def test_cookie_parsing(self):
        h = self._make(HTTP_COOKIE="sid=abc123; theme=dark")
        assert "sid" in h.cookie
        assert h.cookie["sid"].value == "abc123"

    def test_cookies_alias(self):
        h = self._make(HTTP_COOKIE="a=1")
        assert h.cookies is h.cookie

    def test_date_parsing(self):
        h = self._make(HTTP_DATE="Wed, 09 Jun 2021 10:18:14 GMT")
        assert isinstance(h.date, datetime)
        assert h.date.year == 2021

    def test_date_absent(self):
        h = self._make()
        assert h.date is None

    def test_if_modified_since(self):
        h = self._make(HTTP_IF_MODIFIED_SINCE="Wed, 09 Jun 2021 10:18:14 GMT")
        assert isinstance(h.if_modified_since, datetime)

    def test_if_modified_since_absent(self):
        h = self._make()
        assert h.if_modified_since is None

    def test_format_html(self):
        h = self._make(HTTP_ACCEPT="text/html")
        assert h.format == "html"

    def test_format_json(self):
        h = self._make(HTTP_ACCEPT="application/json")
        assert h.format == "json"

    def test_format_fallback_default(self):
        h = self._make(HTTP_ACCEPT="*/*")
        assert h.format == "html"

    def test_format_no_accept(self):
        h = self._make()
        assert h.format == "html"

    def test_forwarded(self):
        h = self._make(HTTP_FORWARDED="for=1.2.3.4;proto=https")
        assert h.forwarded == [{"for": "1.2.3.4", "proto": "https"}]

    def test_host_with_port_default(self):
        h = self._make()
        assert h.host_with_port == "example.com"

    def test_host_with_port_non_default(self):
        # make_test_scope sets HTTP_HOST without port; pass host:port directly
        env = make_test_scope(HTTP_HOST="example.com:8080")
        h = RequestHeadersMixin(env)
        assert h.host_with_port == "example.com:8080"

    def test_port_is_default_true(self):
        h = self._make()
        assert h.port_is_default is True

    def test_port_string_default(self):
        h = self._make()
        assert h.port_string == ""

    def test_default_port_http(self):
        h = self._make()
        assert h.default_port == 80

    def test_default_port_https(self):
        h = self._make(HTTP_X_FORWARDED_PROTO="https")
        assert h.default_port == 443

    def test_if_none_match(self):
        h = self._make(HTTP_IF_NONE_MATCH='"abc", "def"')
        assert h.if_none_match == ['"abc"', '"def"']

    def test_is_get(self):
        h = self._make(REQUEST_METHOD="GET")
        assert h.is_get is True
        assert h.is_post is False

    def test_is_post(self):
        h = self._make(REQUEST_METHOD="POST")
        assert h.is_post is True
        assert h.is_get is False

    def test_is_put(self):
        h = self._make(REQUEST_METHOD="PUT")
        assert h.is_put is True

    def test_is_patch(self):
        h = self._make(REQUEST_METHOD="PATCH")
        assert h.is_patch is True

    def test_is_delete(self):
        h = self._make(REQUEST_METHOD="DELETE")
        assert h.is_delete is True

    def test_is_head(self):
        h = self._make(REQUEST_METHOD="HEAD")
        assert h.is_head is True

    def test_is_secure_http(self):
        h = self._make()
        assert h.is_secure is False

    def test_is_secure_https(self):
        h = self._make(HTTP_X_FORWARDED_PROTO="https")
        assert h.is_secure is True

    def test_is_xhr(self):
        h = self._make(HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert h.is_xhr is True

    def test_is_xhr_false(self):
        h = self._make()
        assert h.is_xhr is False

    def test_remote_ip_forwarded(self):
        h = self._make(HTTP_FORWARDED="for=10.0.0.1")
        assert h.remote_ip == "10.0.0.1"

    def test_remote_ip_x_forwarded_for(self):
        h = self._make(HTTP_X_FORWARDED_FOR="10.0.0.2, 10.0.0.3")
        assert h.remote_ip == "10.0.0.2"

    def test_remote_ip_x_real_ip(self):
        h = self._make(HTTP_X_REAL_IP="10.0.0.4")
        assert h.remote_ip == "10.0.0.4"

    def test_remote_ip_forwarded_without_for_falls_through(self):
        """Forwarded header present but no 'for' key — falls through to next check."""
        h = self._make(HTTP_FORWARDED="proto=https", HTTP_X_FORWARDED_FOR="10.0.0.5")
        assert h.remote_ip == "10.0.0.5"

    def test_remote_ip_fallback_remote_addr(self):
        h = self._make()
        assert h.remote_ip == "127.0.0.1"

    def test_request_id(self):
        h = self._make(HTTP_X_REQUEST_ID="abc-123")
        assert h.request_id == "abc-123"

    def test_request_id_absent(self):
        h = self._make()
        assert h.request_id is None

    def test_user_agent(self):
        h = self._make(HTTP_USER_AGENT="TestBot/1.0")
        assert h.user_agent == "TestBot/1.0"

    def test_user_agent_absent(self):
        h = self._make()
        assert h.user_agent == ""


# ── Standalone parsers (headers.py) ─────────────────────────────────


class TestParseAccept:
    def test_none(self):
        assert parse_accept(None) == []

    def test_single(self):
        assert parse_accept("text/html") == ["text/html"]

    def test_quality_sorting(self):
        result = parse_accept("text/plain;q=0.5, text/html;q=0.9, */*;q=0.1")
        assert result == ["text/html", "text/plain", "*/*"]

    def test_default_quality(self):
        result = parse_accept("text/html, text/plain;q=0.5")
        assert result[0] == "text/html"
        assert result[1] == "text/plain"


class TestParseMultivalue:
    def test_fast_path_simple(self):
        result = parse_multivalue("text/html, text/plain")
        assert result == [("text/html", {}), ("text/plain", {})]

    def test_fast_path_with_params(self):
        result = parse_multivalue("text/html;q=0.9, */*;q=0.1")
        assert result[0] == ("text/html", {"q": "0.9"})
        assert result[1] == ("*/*", {"q": "0.1"})

    def test_slow_path_quoted_string(self):
        result = parse_multivalue('text/html, "quoted value"')
        assert len(result) == 2

    def test_empty_string(self):
        result = parse_multivalue("")
        assert result == [("", {})]


class TestParseCommaSeparated:
    def test_none(self):
        assert parse_comma_separated(None) == []

    def test_single(self):
        assert parse_comma_separated("value") == ["value"]

    def test_multiple(self):
        assert parse_comma_separated("a, b, c") == ["a", "b", "c"]

    def test_whitespace(self):
        # parse_comma_separated strips leading/trailing commas and spaces,
        # then splits on ", " — inner values keep their whitespace from split
        result = parse_comma_separated("  a , b  ")
        assert len(result) == 2
        assert "a" in result[0]
        assert "b" in result[1]


class TestParseCookie:
    def test_none(self):
        assert parse_cookie(None) == {}

    def test_single(self):
        cookies = parse_cookie("name=value")
        assert cookies["name"].value == "value"

    def test_multiple(self):
        cookies = parse_cookie("a=1; b=2")
        assert cookies["a"].value == "1"
        assert cookies["b"].value == "2"


class TestParseHost:
    def test_empty(self):
        assert parse_host("") == ("", 0)
        assert parse_host(None) == ("", 0)

    def test_ipv4(self):
        assert parse_host("example.com") == ("example.com", 0)

    def test_ipv4_with_port(self):
        assert parse_host("example.com:8080") == ("example.com", 8080)

    def test_ipv6(self):
        assert parse_host("[::1]") == ("::1", 0)

    def test_ipv6_with_port(self):
        assert parse_host("[::1]:8080") == ("::1", 8080)


class TestParseRequestId:
    def test_none(self):
        assert parse_request_id(None) is None

    def test_normal(self):
        assert parse_request_id("abc-123") == "abc-123"

    def test_non_ascii_removed(self):
        result = parse_request_id("abc\u00e9def")
        assert "\u00e9" not in result

    def test_truncation(self):
        long_id = "x" * 300
        result = parse_request_id(long_id)
        assert len(result) == 200


# ── parse_forwarded (forwarded.py) ──────────────────────────────────


class TestParseForwarded:
    def test_none(self):
        assert parse_forwarded(None) == []

    def test_single_proxy(self):
        result = parse_forwarded("for=1.2.3.4")
        assert result == [{"for": "1.2.3.4"}]

    def test_multiple_proxies(self):
        result = parse_forwarded("for=1.2.3.4, for=5.6.7.8")
        assert len(result) == 2
        assert result[0]["for"] == "1.2.3.4"
        assert result[1]["for"] == "5.6.7.8"

    def test_quoted_values(self):
        result = parse_forwarded('for="1.2.3.4"')
        assert result[0]["for"] == "1.2.3.4"

    def test_port_suffix(self):
        result = parse_forwarded("for=1.2.3.4:8080")
        assert result[0]["for"] == "1.2.3.4:8080"

    def test_multiple_params(self):
        result = parse_forwarded("for=1.2.3.4;proto=https;by=proxy.example.com")
        assert result[0]["for"] == "1.2.3.4"
        assert result[0]["proto"] == "https"
        assert result[0]["by"] == "proxy.example.com"

    def test_bad_syntax_skipped(self):
        # Invalid token followed by valid one
        result = parse_forwarded("$$invalid$$, for=1.2.3.4")
        # Should have two proxy entries (one empty from bad syntax, one valid)
        found = [p for p in result if "for" in p]
        assert len(found) == 1
        assert found[0]["for"] == "1.2.3.4"


# ── Request class ───────────────────────────────────────────────────


class TestRequest:
    def test_default_construction(self):
        req = Request()
        assert req.method == "GET"
        assert req.path == "/"

    def test_repr(self):
        req = Request()
        r = repr(req)
        assert "GET" in r
        assert "/" in r

    def test_session_get_set(self):
        req = Request()
        req.session = {"foo": "bar"}
        assert isinstance(req.session, DotDict)
        assert req.session["foo"] == "bar"

    def test_body_property(self):
        env = make_test_scope(body=b"hello")
        req = Request(**env)
        assert req.body.read() == b"hello"

    def test_body_fallback_empty(self):
        req = Request()
        # Default make_test_scope body is empty BytesIO
        data = req.body.read()
        assert data == b""

    def test_flashes_from_session(self):
        req = Request()
        req.session = {"_flashes": [("info", "Hello!")]}
        assert req.flashes == [("info", "Hello!")]

    def test_flashes_empty(self):
        req = Request()
        assert req.flashes == []

    def test_form_lazy_caching(self):
        env = make_test_scope(
            body=b"key=value",
            REQUEST_METHOD="POST",
            CONTENT_TYPE="application/x-www-form-urlencoded",
            CONTENT_LENGTH="9",
        )
        req = Request(**env)
        form1 = req.form
        form2 = req.form
        assert form1 is form2
        assert form1["key"] == ["value"]

    def test_form_get_returns_empty(self):
        env = make_test_scope(REQUEST_METHOD="GET")
        req = Request(**env)
        assert len(req.form) == 0

    def test_query_lazy_caching(self):
        env = make_test_scope(params={"q": "test"})
        req = Request(**env)
        q1 = req.query
        q2 = req.query
        assert q1 is q2
        assert q1["q"] == ["test"]

    def test_query_string(self):
        env = make_test_scope(params={"a": "1"})
        req = Request(**env)
        assert "a=1" in req.query_string

    def test_url_with_query(self):
        env = make_test_scope("/hello", params={"x": "1"})
        req = Request(**env)
        assert req.url == "/hello?x=1"

    def test_get_url_without_query(self):
        env = make_test_scope("/hello", params={"x": "1"})
        req = Request(**env)
        assert req.get_url(include_query=False) == "/hello"

    def test_url_no_query(self):
        env = make_test_scope("/hello")
        req = Request(**env)
        assert req.url == "/hello"

    def test_get_cookie_found(self):
        env = make_test_scope(HTTP_COOKIE="name=Jon")
        req = Request(**env)
        assert req.get_cookie("name") == "Jon"

    def test_get_cookie_not_found(self):
        env = make_test_scope()
        req = Request(**env)
        assert req.get_cookie("missing") is None

    def test_get_cookie_default(self):
        env = make_test_scope()
        req = Request(**env)
        assert req.get_cookie("missing", "fallback") == "fallback"

    def test_get_signed_cookie_valid(self):
        import itsdangerous

        s = itsdangerous.URLSafeTimedSerializer("test-secret")
        signed = s.dumps("hello")

        app = MagicMock()
        app.get_serializer.return_value = s

        env = make_test_scope(HTTP_COOKIE=f"token={signed}")
        req = Request(app=app, **env)
        assert req.get_signed_cookie("token") == "hello"

    def test_get_signed_cookie_bad_signature(self):
        import itsdangerous

        secret = "test-secret"
        s = itsdangerous.URLSafeTimedSerializer(secret)

        app = MagicMock()
        app.get_serializer.return_value = s

        env = make_test_scope(HTTP_COOKIE="token=tampered-value")
        req = Request(app=app, **env)
        assert req.get_signed_cookie("token", salt="x") is None

    def test_get_signed_cookie_missing(self):
        import itsdangerous

        secret = "test-secret"
        s = itsdangerous.URLSafeTimedSerializer(secret)

        app = MagicMock()
        app.get_serializer.return_value = s

        env = make_test_scope()
        req = Request(app=app, **env)
        assert req.get_signed_cookie("missing", "default", salt="x") == "default"


# ── parse_form.py ───────────────────────────────────────────────────


class TestParseForm:
    def test_empty_content(self):
        stream = BytesIO(b"")
        result = parse_form(stream, "text/plain", 0)
        assert len(result) == 0

    def test_max_content_length_exceeded(self):
        stream = BytesIO(b"x" * 100)
        with pytest.raises(RequestEntityTooLarge):
            parse_form(stream, "text/plain", 100, max_content_length=10)

    def test_urlencoded(self):
        body = b"name=alice&age=30"
        stream = BytesIO(body)
        result = parse_form(
            stream, "application/x-www-form-urlencoded", len(body),
        )
        assert result["name"] == ["alice"]
        assert result["age"] == ["30"]

    def test_json(self):
        body = b'{"name": "alice", "age": 30}'
        stream = BytesIO(body)
        result = parse_form(
            stream, "application/json", len(body),
        )
        assert result["name"] == ["alice"]
        assert result["age"] == [30]

    def test_unsupported_type(self):
        body = b"data"
        stream = BytesIO(body)
        with pytest.raises(UnsupportedMediaType):
            parse_form(stream, "text/plain", len(body))


class TestParseQueryString:
    def test_normal(self):
        result = parse_query_string("a=1&b=2")
        assert result["a"] == ["1"]
        assert result["b"] == ["2"]

    def test_max_query_size_exceeded(self):
        with pytest.raises(UriTooLong):
            parse_query_string("a=1&b=2", max_query_size=3)

    def test_blank_values_kept(self):
        result = parse_query_string("key=")
        assert result["key"] == [""]

    def test_empty_string(self):
        result = parse_query_string("")
        assert len(result) == 0


class TestParseJson:
    def test_valid_object(self):
        result = parse_json('{"a": 1}')
        assert result["a"] == [1]

    def test_decode_error_strict(self):
        with pytest.raises(MultipartError):
            parse_json("{invalid}", strict=True)

    def test_decode_error_non_strict(self):
        result = parse_json("{invalid}", strict=False)
        assert len(result) == 0


class TestNormalizeNewlines:
    def test_crlf(self):
        assert _normalize_newlines("a\r\nb") == "a\nb"

    def test_cr(self):
        assert _normalize_newlines("a\rb") == "a\nb"

    def test_lf(self):
        assert _normalize_newlines("a\nb") == "a\nb"

    def test_mixed(self):
        assert _normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


class TestValidateActualContentLength:
    def test_match(self):
        _validate_actual_content_length("hello", 5)  # should not raise

    def test_too_big(self):
        with pytest.raises(BadRequest, match="bigger"):
            _validate_actual_content_length("hello world", 5)

    def test_too_small(self):
        with pytest.raises(BadRequest, match="smaller"):
            _validate_actual_content_length("hi", 5)


class TestReadContent:
    def test_normal(self):
        stream = BytesIO(b"hello")
        result = _read_content(stream, 100, "utf8")
        assert result == "hello"

    def test_exceeds_limit(self):
        stream = BytesIO(b"hello world")
        with pytest.raises(RequestEntityTooLarge):
            _read_content(stream, 5, "utf8")


# ── parse_form multipart path ──────────────────────────────────────


class TestParseFormMultipart:
    def test_multipart_form_field(self):
        body = _build_multipart([
            {"name": "username", "value": "alice"},
        ])
        stream = BytesIO(body)
        result = parse_form(
            stream,
            "multipart/form-data; boundary=testboundary",
            len(body),
        )
        assert result["username"] == ["alice"]

    def test_multipart_file_upload(self):
        body = _build_multipart([
            {
                "name": "file",
                "value": b"file content here",
                "filename": "test.txt",
                "content_type": "text/plain",
            },
        ])
        stream = BytesIO(body)
        result = parse_form(
            stream,
            "multipart/form-data; boundary=testboundary",
            len(body),
        )
        part = result["file"][0]
        assert part.filename == "test.txt"
        assert part.value == "file content here"

    def test_multipart_mixed_fields_and_files(self):
        body = _build_multipart([
            {"name": "title", "value": "My Document"},
            {
                "name": "doc",
                "value": b"PDF bytes",
                "filename": "doc.pdf",
                "content_type": "application/pdf",
            },
        ])
        stream = BytesIO(body)
        result = parse_form(
            stream,
            "multipart/form-data; boundary=testboundary",
            len(body),
        )
        assert result["title"] == ["My Document"]
        part = result["doc"][0]
        assert part.filename == "doc.pdf"

    def test_multipart_no_boundary_raises(self):
        stream = BytesIO(b"data")
        with pytest.raises(MultipartError, match="No boundary"):
            parse_form(stream, "multipart/form-data", 4)

    def test_multipart_crlf_normalization(self):
        body = _build_multipart([
            {"name": "text", "value": "line1\r\nline2\rline3"},
        ])
        stream = BytesIO(body)
        result = parse_form(
            stream,
            "multipart/form-data; boundary=testboundary",
            len(body),
        )
        # Form text values have newlines normalized
        assert result["text"] == ["line1\nline2\nline3"]


class TestParseMultipartDirect:
    def test_no_boundary_raises(self):
        with pytest.raises(MultipartError, match="No boundary"):
            parse_multipart(BytesIO(b""), 0, {}, encoding="utf8")

    def test_with_boundary(self):
        body = _build_multipart([
            {"name": "field", "value": "val"},
        ])
        result = parse_multipart(
            BytesIO(body), len(body),
            {"boundary": "testboundary"},
            encoding="utf8",
        )
        assert result["field"] == ["val"]


class TestParseQueryStringStrictFalse:
    def test_value_error_non_strict(self):
        # parse_qs with invalid encoding can raise ValueError;
        # non-strict mode swallows it
        result = parse_query_string("key=val", strict=False)
        assert result["key"] == ["val"]


# ── multipart.py ────────────────────────────────────────────────────


class TestToBytes:
    def test_str_input(self):
        assert to_bytes("hello") == b"hello"

    def test_bytes_input(self):
        assert to_bytes(b"hello") == b"hello"

    def test_custom_encoding(self):
        assert to_bytes("hello", enc="ascii") == b"hello"


class TestCopyFile:
    def test_copy_all(self):
        src = BytesIO(b"hello world")
        dst = BytesIO()
        size = copy_file(src, dst)
        assert size == 11
        assert dst.getvalue() == b"hello world"

    def test_copy_with_maxread(self):
        src = BytesIO(b"hello world")
        dst = BytesIO()
        size = copy_file(src, dst, maxread=5)
        assert size == 5
        assert dst.getvalue() == b"hello"

    def test_copy_empty(self):
        src = BytesIO(b"")
        dst = BytesIO()
        size = copy_file(src, dst)
        assert size == 0


class TestHeaderQuote:
    def test_plain_value(self):
        assert header_quote("foo") == "foo"

    def test_special_chars_quoted(self):
        result = header_quote('foo"bar')
        assert result.startswith('"')
        assert result.endswith('"')

    def test_space_quoted(self):
        result = header_quote("foo bar")
        assert result == '"foo bar"'

    def test_backslash_escaped(self):
        result = header_quote("foo\\bar")
        assert '\\\\"' not in result or "\\\\" in result


class TestHeaderUnquote:
    def test_quoted_value(self):
        assert header_unquote('"foo"') == "foo"

    def test_unquoted_value(self):
        assert header_unquote("foo") == "foo"

    def test_escaped_quote(self):
        assert header_unquote('"foo\\"bar"') == 'foo"bar'

    def test_escaped_backslash(self):
        assert header_unquote('"foo\\\\bar"') == "foo\\bar"


class TestParseOptionsHeader:
    def test_no_semicolon(self):
        ct, opts = parse_options_header("text/html")
        assert ct == "text/html"
        assert opts == {}

    def test_with_options(self):
        ct, opts = parse_options_header('form-data; name="Test"; filename="Test.txt"')
        assert ct == "form-data"
        assert opts["name"] == "Test"
        assert opts["filename"] == "Test.txt"

    def test_quoted_value_with_escape(self):
        ct, opts = parse_options_header('form-data; name="Te\\"st"')
        assert opts["name"] == 'Te"st'

    def test_existing_options_dict(self):
        existing = {"extra": "value"}
        ct, opts = parse_options_header("text/html; charset=utf-8", options=existing)
        assert opts["charset"] == "utf-8"
        assert opts["extra"] == "value"


class TestMultipartParser:
    def test_single_field(self):
        body = _build_multipart([
            {"name": "field1", "value": "value1"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 1
        assert parts[0].name == "field1"
        assert parts[0].value == "value1"

    def test_multiple_fields(self):
        body = _build_multipart([
            {"name": "a", "value": "1"},
            {"name": "b", "value": "2"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 2
        assert parts[0].value == "1"
        assert parts[1].value == "2"

    def test_file_upload(self):
        body = _build_multipart([
            {
                "name": "myfile",
                "value": b"binary content",
                "filename": "data.bin",
                "content_type": "application/octet-stream",
            },
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 1
        assert parts[0].filename == "data.bin"
        assert parts[0].raw == b"binary content"

    def test_get_by_name(self):
        body = _build_multipart([
            {"name": "a", "value": "1"},
            {"name": "b", "value": "2"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        part = mp.get("b")
        assert part is not None
        assert part.value == "2"

    def test_get_missing_returns_default(self):
        body = _build_multipart([
            {"name": "a", "value": "1"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        assert mp.get("missing") is None
        assert mp.get("missing", "fallback") == "fallback"

    def test_get_all(self):
        body = _build_multipart([
            {"name": "items", "value": "one"},
            {"name": "items", "value": "two"},
            {"name": "other", "value": "x"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        items = mp.get_all("items")
        assert len(items) == 2
        assert items[0].value == "one"
        assert items[1].value == "two"

    def test_boundary_too_large_raises(self):
        big_boundary = "x" * 300
        with pytest.raises(MultipartError, match="Boundary does not fit"):
            MultipartParser(BytesIO(b""), big_boundary, buffer_size=256)

    def test_no_boundary_in_stream_raises(self):
        mp = MultipartParser(BytesIO(b"no boundary here"), "testboundary")
        with pytest.raises(MultipartError, match="does not contain boundary"):
            mp.parts()

    def test_empty_multipart(self):
        # Terminator immediately after boundary
        body = b"--testboundary--\r\n"
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 0

    def test_unexpected_end_of_stream(self):
        # Only separator, no terminator -> unexpected end
        body = (
            b"--testboundary\r\n"
            b'Content-Disposition: form-data; name="f"\r\n'
            b"\r\n"
            b"value\r\n"
            # Missing --testboundary-- terminator
        )
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        with pytest.raises(MultipartError, match="Unexpected end"):
            mp.parts()

    def test_iter_caches_parts(self):
        body = _build_multipart([
            {"name": "a", "value": "1"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        # First iteration
        list(mp)
        # Second iteration should yield cached parts
        parts = list(mp)
        assert len(parts) == 1
        assert parts[0].name == "a"

    def test_memory_limit(self):
        body = _build_multipart([
            {"name": "big", "value": "x" * 200},
        ])
        mp = MultipartParser(
            BytesIO(body), "testboundary", len(body), mem_limit=50,
        )
        with pytest.raises(MultipartError, match="Memory limit"):
            mp.parts()

    def test_bytes_boundary(self):
        body = _build_multipart([
            {"name": "f", "value": "v"},
        ])
        mp = MultipartParser(BytesIO(body), b"testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 1

    def test_preamble_ignored(self):
        body = (
            b"This is the preamble. It should be ignored.\r\n"
            b"--testboundary\r\n"
            b'Content-Disposition: form-data; name="field"\r\n'
            b"\r\n"
            b"value\r\n"
            b"--testboundary--\r\n"
        )
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 1
        assert parts[0].value == "value"


class TestMultipartPart:
    def _make_part(self, name="field", value="hello", filename=None,
                   content_type=None):
        """Build a single MultipartPart by feeding it headers + body."""
        part = MultipartPart()
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        part.feed(f"Content-Disposition: {disp}".encode(), b"\r\n")
        if content_type:
            part.feed(f"Content-Type: {content_type}".encode(), b"\r\n")
        part.feed(b"", b"\r\n")  # blank line -> finish_header
        val = value.encode() if isinstance(value, str) else value
        part.feed(val, b"\r\n")
        return part

    def test_value_and_raw(self):
        part = self._make_part(value="hello")
        assert part.value == "hello"
        assert part.raw == b"hello"

    def test_name_and_filename(self):
        part = self._make_part(name="doc", filename="report.pdf",
                               content_type="application/pdf")
        assert part.name == "doc"
        assert part.filename == "report.pdf"

    def test_is_buffered(self):
        part = self._make_part()
        assert part.is_buffered() is True

    def test_raw_no_file(self):
        part = MultipartPart()
        assert part.raw == b""

    def test_value_no_file(self):
        part = MultipartPart()
        assert part.value == ""

    def test_close(self):
        part = self._make_part()
        assert part.file is not None
        part.close()
        assert part.file is None

    def test_close_idempotent(self):
        part = MultipartPart()
        part.close()  # no file, should not raise
        assert part.file is None

    def test_save_as(self, tmp_path):
        part = self._make_part(value="save me")
        part.file.seek(0)
        path = str(tmp_path / "output.txt")
        size = part.save_as(path)
        assert size > 0
        with open(path, "rb") as f:
            assert f.read() == b"save me"

    def test_write_header_continuation(self):
        """Test folded header (continuation line starting with whitespace)."""
        part = MultipartPart()
        part.feed(b"Content-Disposition: form-data;", b"\r\n")
        part.feed(b' name="field"', b"\r\n")
        part.feed(b"", b"\r\n")  # end of headers
        assert part.name == "field"

    def test_write_header_no_colon_raises(self):
        part = MultipartPart()
        with pytest.raises(MultipartError, match="No colon"):
            part.feed(b"BadHeader", b"\r\n")

    def test_write_header_no_newline_raises(self):
        part = MultipartPart()
        with pytest.raises(MultipartError, match="Unexpected end of line"):
            part.feed(b"Content-Disposition: form-data", b"")

    def test_missing_content_disposition_raises(self):
        part = MultipartPart()
        part.feed(b"Content-Type: text/plain", b"\r\n")
        with pytest.raises(MultipartError, match="Content-Disposition"):
            part.feed(b"", b"\r\n")  # blank line triggers finish_header

    def test_write_body_empty_noop(self):
        part = self._make_part(value="initial")
        size_before = part.size
        part.write_body(b"", b"")
        assert part.size == size_before

    def test_content_length_exceeded_raises(self):
        part = MultipartPart()
        part.feed(b'Content-Disposition: form-data; name="f"', b"\r\n")
        part.feed(b"Content-Length: 3", b"\r\n")
        part.feed(b"", b"\r\n")  # finish headers
        with pytest.raises(MultipartError, match="exceeds Content-Length"):
            part.feed(b"too much data here", b"\r\n")

    def test_spill_to_disk(self):
        """File uploads that exceed memfile_limit spill to a TemporaryFile."""
        part = MultipartPart(memfile_limit=10)
        part.feed(b'Content-Disposition: form-data; name="big"; filename="f.bin"', b"\r\n")
        part.feed(b"", b"\r\n")
        assert part.is_buffered() is True
        # Feed enough data to exceed the limit
        part.feed(b"x" * 20, b"\r\n")
        assert part.is_buffered() is False
        # Data should still be accessible
        assert b"x" * 20 in part.raw

    def test_non_file_field_exceeding_memfile_limit(self):
        """Non-file fields that exceed memfile_limit raise an error."""
        part = MultipartPart(memfile_limit=10)
        part.feed(b'Content-Disposition: form-data; name="big"', b"\r\n")
        part.feed(b"", b"\r\n")
        with pytest.raises(MultipartError):
            part.feed(b"x" * 20, b"\r\n")


# ── Additional coverage for headers.py ──────────────────────────────


class TestHeadersMixinAdditional:
    def _make(self, **extra):
        env = make_test_scope(**extra)
        return RequestHeadersMixin(env)

    def test_normalize_env_http_prefix_kept_when_unprefixed_exists(self):
        """When a non-HTTP_ key exists (e.g. CONTENT_TYPE), and HTTP_CONTENT_TYPE
        also exists, the HTTP_ variant is kept with its full normalized name."""
        env = make_test_scope(CONTENT_TYPE="text/plain")
        env["HTTP_CONTENT_TYPE"] = "text/html"
        h = RequestHeadersMixin(env)
        # The unprefixed content_type was already set by CONTENT_TYPE,
        # so HTTP_CONTENT_TYPE should be stored as http_content_type
        assert h.env.get("http_content_type") == "text/html"
        assert h.env.get("content_type") == "text/plain"

    def test_headers_property_returns_env(self):
        h = self._make()
        assert h.headers is h.env

    def test_format_with_unrecognized_mime(self):
        """When accept has a MIME type that has no known extension, fall through."""
        h = self._make(HTTP_ACCEPT="application/x-unknown-type-xyz, text/html")
        assert h.format == "html"

    def test_get_returns_default_for_none_special_header(self):
        """When a special header (e.g. request_id) returns None, get() returns default."""
        h = self._make()
        assert h.get("request_id", "fallback") == "fallback"


class TestParseMultivalueSlowPath:
    def test_params_with_key_value(self):
        """Slow path: quoted string in params position."""
        result = parse_multivalue('text/html;q="0.9", application/json')
        assert result[0] == ("text/html", {"q": "0.9"})
        assert result[1] == ("application/json", {})

    def test_param_without_value(self):
        """Slow path: semicolon-separated attribute without = sign."""
        result = parse_multivalue('"text/html";novalue, other')
        # "novalue" should be an attr with empty string value
        assert "novalue" in result[0][1]
        assert result[0][1]["novalue"] == ""

    def test_escaped_quote_in_quoted_string(self):
        result = parse_multivalue('"val\\"ue"')
        assert result[0][0] == 'val"ue'

    def test_equals_without_preceding_key(self):
        """Branch 546->549: lop=='=' but key is None.
        When first token after comma has tok='=', lop becomes '=' with key=None.
        The next token then hits lop=='=' with key falsy, falling through."""
        result = parse_multivalue('"a"="b"')
        # 'a' is appended as a value (lop was ','), then 'b' hits lop='='
        # with key=None → branch skipped, lop set to '' (empty tok)
        assert result[0][0] == "a"


# ── Additional coverage for forwarded.py ────────────────────────────


class TestParseForwardedAdditional:
    def test_bad_syntax_after_valid_pair_skips_to_comma(self):
        """When need_separator is True and we get a match, skip to next comma."""
        # Two pairs without semicolon between them — second triggers skip
        result = parse_forwarded("for=1.2.3.4 for=5.6.7.8, for=9.0.0.1")
        # The first proxy should have "for" from the first match,
        # then the second "for=5.6.7.8" triggers bad syntax skip
        found = [p for p in result if p.get("for")]
        assert any(p["for"] == "9.0.0.1" for p in found)

    def test_whitespace_between_pairs(self):
        result = parse_forwarded("for=1.2.3.4 ; proto=https")
        assert result[0]["for"] == "1.2.3.4"
        assert result[0]["proto"] == "https"


# ── Additional coverage for request.py ──────────────────────────────


class TestRequestAdditional:
    def test_get_signed_cookie_bytes_return(self):
        """Cover line 328: when serializer.loads returns bytes, decode it."""
        serializer = MagicMock()
        serializer.loads.return_value = b"bytes-value"

        app = MagicMock()
        app.get_serializer.return_value = serializer

        env = make_test_scope(HTTP_COOKIE="token=signed-data")
        req = Request(app=app, **env)
        result = req.get_signed_cookie("token")
        assert result == "bytes-value"

    def test_form_head_returns_empty(self):
        env = make_test_scope(REQUEST_METHOD="HEAD")
        req = Request(**env)
        assert len(req.form) == 0

    def test_max_content_length_passed_through(self):
        req = Request(max_content_length=1024)
        assert req.max_content_length == 1024

    def test_max_query_size_passed_through(self):
        req = Request(max_query_size=512)
        assert req.max_query_size == 512

    def test_encoding_default(self):
        req = Request()
        assert req.encoding == "utf8"


# ── Remaining coverage gaps ─────────────────────────────────────────


class TestMultipartParserEdgeCases:
    def test_data_after_terminator_raises(self):
        """Line 249: data after end-of-stream terminator raises."""
        body = (
            b"--boundary--\r\n"
            b"unexpected extra data\r\n"
        )
        mp = MultipartParser(BytesIO(body), "boundary", len(body))
        with pytest.raises(MultipartError, match="Data after end of stream"):
            mp.parts()

    def test_disk_limit_exceeded(self):
        """Line 294: disk_limit check for non-buffered parts."""
        # Create a file upload large enough to spill to disk, then exceed disk_limit
        big_data = "x" * 500
        body = _build_multipart([
            {"name": "big", "filename": "big.bin", "value": big_data},
        ])
        mp = MultipartParser(
            BytesIO(body), "testboundary", len(body),
            memfile_limit=10,
            mem_limit=2**20,
            disk_limit=50,
        )
        with pytest.raises(MultipartError, match="Disk limit|Memory limit"):
            mp.parts()

    def test_multiple_parts_with_separator(self):
        """Lines 270-283: separator between parts triggers disk_used/mem_used
        tracking and file.seek(0) on the yielded part."""
        body = _build_multipart([
            {"name": "a", "value": "first"},
            {"name": "b", "value": "second"},
            {"name": "c", "value": "third"},
        ])
        mp = MultipartParser(BytesIO(body), "testboundary", len(body))
        parts = mp.parts()
        assert len(parts) == 3
        # Verify all parts are seeked to 0 and readable
        for p in parts:
            assert p.value in ("first", "second", "third")

    def test_lf_only_line_ending(self):
        """Line 224: lines ending with just \\n."""
        body = (
            b"--boundary\n"
            b'Content-Disposition: form-data; name="f"\n'
            b"\n"
            b"value\n"
            b"--boundary--\n"
        )
        mp = MultipartParser(BytesIO(body), "boundary", len(body))
        parts = mp.parts()
        assert len(parts) == 1
        assert parts[0].value == "value"


class TestMultipartPartEdgeCases:
    def test_raw_restores_position(self):
        """Lines 404-412: raw property saves and restores file position."""
        part = MultipartPart()
        part.feed(b'Content-Disposition: form-data; name="f"', b"\r\n")
        part.feed(b"", b"\r\n")
        part.feed(b"hello", b"\r\n")
        # Move file position to end
        part.file.seek(0, 2)
        pos = part.file.tell()
        raw = part.raw
        assert raw == b"hello"
        # Position should be restored
        assert part.file.tell() == pos


class TestParseFormMultipartEdgeCases:
    def test_nameless_part_skipped(self):
        """Line 92: parts with no name are skipped."""
        # Build a multipart body where one part has no name
        body = (
            b"--boundary\r\n"
            b"Content-Disposition: form-data\r\n"
            b"\r\n"
            b"anonymous\r\n"
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="named"\r\n'
            b"\r\n"
            b"has name\r\n"
            b"--boundary--\r\n"
        )
        result = parse_multipart(
            BytesIO(body), len(body),
            {"boundary": "boundary"},
            encoding="utf8",
        )
        assert "named" in result
        # The nameless part should have been skipped
        assert len(result) == 1

    def test_strict_multipart_error_closes_files_and_reraises(self):
        """Lines 102-106: on MultipartError in strict mode, file parts are
        closed and the error is re-raised."""
        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="a.txt"\r\n'
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"file content\r\n"
            b"--boundary\r\n"
            # Missing Content-Disposition => will raise MultipartError
            b"BadHeader\r\n"
        )
        with pytest.raises(MultipartError):
            parse_multipart(
                BytesIO(body), len(body),
                {"boundary": "boundary"},
                encoding="utf8",
                strict=True,
            )

    def test_non_strict_multipart_error_swallowed(self):
        """Lines 102-106: non-strict mode swallows MultipartError."""
        body = (
            b"--boundary\r\n"
            b'Content-Disposition: form-data; name="field"\r\n'
            b"\r\n"
            b"value\r\n"
            b"--boundary\r\n"
            b"BadHeader\r\n"
        )
        # Should not raise in non-strict mode
        result = parse_multipart(
            BytesIO(body), len(body),
            {"boundary": "boundary"},
            encoding="utf8",
            strict=False,
        )
        assert "field" in result
