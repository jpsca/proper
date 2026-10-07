import datetime
import time

import pytest

from proper import App, current
from proper.core.request import Request
from proper.core.request.formparser import (
    _safe_decode,
    parse_json,
    parse_options_header,
    parse_query_string,
)
from proper.core.request.headers import parse_host, parse_request_id
from proper.errors import (
    InvalidHeader,
    MultipartError,
    UriTooLong,
)
from proper.test_client import make_test_request


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

    @pytest.mark.parametrize("header", [
        "Multipart/Form-Data; Boundary=x",
        "MULTIPART/FORM-DATA; BOUNDARY=x",
        " multipart/form-data ;boundary=x",
    ])
    def test_media_type_and_parameter_names_are_case_insensitive(self, header):
        """RFC 9110 §8.3.1: the type, subtype and parameter names are
        case-insensitive. The value keeps its case."""
        ct, opts = parse_options_header(header)
        assert ct == "multipart/form-data"
        assert opts == {"boundary": "x"}


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

    @pytest.mark.parametrize("content", [
        "[1, 2]",
        '[["a", 1]]',
        '["ab"]',
        "[]",
        '"x"',
        "3",
        "true",
        "null",
    ])
    def test_not_an_object_gives_an_empty_form(self, content):
        """Only the members of an object are form fields. Any other JSON
        value is valid but has no fields; the controller can read it from
        `request.body`."""
        result = parse_json(content)
        assert len(result) == 0


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
        assert result and len(result) == 200


# ----


def _make_request(url="/", method="GET", **kw):
    return make_test_request(url, method=method, **kw)


def test_method_and_path():
    req = _make_request("/hello", method="POST")
    assert req.method == "POST"
    assert req.request_method == "POST"
    assert req.path == "/hello"


def test_content_type():
    req = _make_request("/", headers=[("content-type", "application/json")])
    assert req.content_type == "application/json"


def test_content_length():
    req = _make_request("/", headers=[("content-length", "42")])
    assert req.content_length == 42


def test_content_length_zero():
    req = _make_request("/")
    assert req.content_length == 0


def test_content_length_invalid():
    with pytest.raises(InvalidHeader, match="number"):
        _make_request("/", headers=[("content-length", "abc")])


def test_content_length_negative():
    with pytest.raises(InvalidHeader, match="positive"):
        _make_request("/", headers=[("content-length", "-1")])


def test_accept():
    req = _make_request("/", headers=[("accept", "text/html,application/json;q=0.5")])
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "application/json"


def test_accept_encoding():
    req = _make_request("/", headers=[("accept-encoding", "gzip,deflate;q=0.5")])
    assert req.accept_encoding[0] == "gzip"


def test_accept_language():
    req = _make_request("/", headers=[("accept-language", "en-US,fr;q=0.5")])
    assert req.accept_language[0] == "en_US"


def test_cookies():
    req = _make_request("/", headers=[("cookie", "a=1; b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


def test_cookies_multiple_headers():
    req = _make_request("/", headers=[("cookie", "a=1"), ("cookie", "b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


def test_cookie_alias():
    req = _make_request("/", headers=[("cookie", "a=1")])
    assert req.cookie == req.cookies


# https://www.rfc-editor.org/info/rfc9110/#section-5.6.7
@pytest.mark.parametrize("value", [
    "Sun, 06 Nov 1994 08:49:37 GMT",   # IMF-fixdate
    "Sunday, 06-Nov-94 08:49:37 GMT",  # obsolete RFC 850 format
    "Sun Nov  6 08:49:37 1994",        # ANSI C's asctime() format
])
def test_date_header(value):
    req = _make_request("/", headers=[("date", value)])
    assert req.date == datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)


def test_date_header_missing():
    req = _make_request("/")
    assert req.date is None


@pytest.mark.parametrize("value", [
    "garbage",
    "",
    "99999999999999999999",
    # The offset moves these out of the range of `datetime`.
    "Fri, 31 Dec 9999 23:59:59 -0100",
    "9999-12-31T23:59:59-01:00",
    "0001-01-01T00:30:00+01:00",
])
def test_invalid_date_is_ignored(value):
    """RFC 9110 §13.1.3: a recipient MUST ignore an invalid date."""
    req = _make_request("/", headers=[("date", value), ("if-modified-since", value)])
    assert req.date is None
    assert req.if_modified_since is None


@pytest.fixture()
def local_time_zone_not_utc(monkeypatch):
    """A local time zone five hours behind UTC, so a date read as local
    time doesn't pass for UTC when the tests run with `TZ=UTC`."""
    monkeypatch.setenv("TZ", "EST5")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.usefixtures("local_time_zone_not_utc")
def test_date_without_a_time_zone_is_utc():
    req = _make_request("/", headers=[("date", "Sun Nov  6 08:49:37 1994")])
    assert req.date == datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)


def test_date_with_an_offset_is_converted_to_utc():
    req = _make_request("/", headers=[("if-modified-since", "Sun, 06 Nov 1994 10:49:37 +0200")])
    assert req.if_modified_since == datetime.datetime(
        1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc
    )


def test_default_port_http():
    req = _make_request("http://example.com/")
    assert req.default_port == 80


def test_default_port_https():
    req = _make_request("https://example.com/")
    assert req.default_port == 443


def test_format_html():
    req = _make_request("/", headers=[("accept", "text/html")])
    assert req.format == "html"


def test_format_json():
    req = _make_request("/", headers=[("accept", "application/json")])
    assert req.format == "json"


def test_format_wildcard_default():
    req = _make_request("/", headers=[("accept", "*/*")])
    assert req.format == "html"


def test_format_no_accept():
    req = _make_request("/")
    assert req.format == "html"


def test_forwarded():
    req = _make_request(
        "/", headers=[("forwarded", "for=192.0.2.60;proto=http;by=203.0.113.43")]
    )
    assert req.forwarded[0]["for"] == "192.0.2.60"


def test_host_with_port_default():
    req = _make_request("http://example.com/")
    assert req.host_with_port == "example.com"


def test_host_with_port_non_default():
    req = _make_request("http://example.com:9090/")
    assert req.host_with_port == "example.com:9090"


def test_if_none_match():
    req = _make_request("/", headers=[("if-none-match", '"etag1", "etag2"')])
    assert '"etag1"' in req.if_none_match
    assert '"etag2"' in req.if_none_match


# https://www.rfc-editor.org/info/rfc9110/#section-5.6.7
@pytest.mark.parametrize("value", [
    "Sun, 06 Nov 1994 08:49:37 GMT",   # IMF-fixdate
    "Sunday, 06-Nov-94 08:49:37 GMT",  # obsolete RFC 850 format
    "Sun Nov  6 08:49:37 1994",        # ANSI C's asctime() format
])
def test_if_modified_since(value):
    req = _make_request("/", headers=[("if-modified-since", value)])
    assert req.if_modified_since == datetime.datetime(1994, 11, 6, 8, 49, 37, tzinfo=datetime.timezone.utc)


def test_if_modified_since_missing():
    req = _make_request("/")
    assert req.if_modified_since is None


def test_is_get():
    assert _make_request("/", method="GET").is_get is True
    assert _make_request("/", method="POST").is_get is False


def test_is_head():
    assert _make_request("/", method="HEAD").is_head is True


def test_is_post():
    assert _make_request("/", method="POST").is_post is True


def test_is_put():
    assert _make_request("/", method="PUT").is_put is True


def test_is_patch():
    assert _make_request("/", method="PATCH").is_patch is True


def test_is_delete():
    assert _make_request("/", method="DELETE").is_delete is True


def test_is_secure_http():
    req = _make_request("http://example.com/")
    assert req.is_secure is False


def test_is_secure_https():
    req = _make_request("https://example.com/")
    assert req.is_secure is True


def test_is_ssl_alias():
    req = _make_request("https://example.com/")
    assert req.is_ssl is True


def test_is_xhr():
    req = _make_request("/", headers=[("x-requested-with", "XMLHttpRequest")])
    assert req.is_xhr is True


def test_is_xhr_false():
    req = _make_request("/")
    assert req.is_xhr is False


def test_turbo_frame():
    req = _make_request("/", headers=[("turbo-frame", "messages")])
    assert req.turbo_frame == "messages"


def test_turbo_frame_none():
    req = _make_request("/")
    assert req.turbo_frame is None


def test_turbo_stream():
    req = _make_request(
        "/", headers=[("accept", "text/vnd.turbo-stream.html, text/html")]
    )
    assert req.turbo_stream is True


def test_turbo_stream_false():
    req = _make_request("/", headers=[("accept", "text/html")])
    assert req.turbo_stream is False


def test_port_is_default():
    assert _make_request("http://example.com/").port_is_default is True
    assert _make_request("http://example.com:9090/").port_is_default is False


def test_port_string():
    assert _make_request("http://example.com/").port_string == ""
    assert _make_request("http://example.com:9090/").port_string == ":9090"


# The peer of a request through a local reverse proxy.
LOCAL_PROXY = ("127.0.0.1", 50000)


@pytest.fixture()
def no_current_app():
    """A request built without an app uses `current.app`, whatever app an
    earlier test left there, and its `TRUSTED_PROXIES`. Start without one,
    so those requests use the default list, and put back the one before
    (`App()` makes itself `current.app`)."""
    previous = current.app
    current.app = None
    yield
    current.app = previous


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_forwarded():
    req = _make_request("/", headers=[("forwarded", "for=1.2.3.4")], client=LOCAL_PROXY)
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_x_forwarded_for():
    req = _make_request(
        "/", headers=[("x-forwarded-for", "5.6.7.8, 10.0.0.1")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "5.6.7.8"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_x_real_ip():
    req = _make_request("/", headers=[("x-real-ip", "9.10.11.12")], client=LOCAL_PROXY)
    assert req.remote_ip == "9.10.11.12"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("header", ["forwarded", "x-forwarded-for", "x-real-ip"])
def test_remote_ip_ignores_forwarding_headers_from_an_untrusted_peer(header):
    """Any client can send these headers: only a trusted proxy's count."""
    value = "for=1.2.3.4" if header == "forwarded" else "1.2.3.4"
    req = _make_request("/", headers=[(header, value)], client=("203.0.113.5", 5000))
    assert req.remote_ip == "203.0.113.5"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("header", ["forwarded", "x-forwarded-for", "x-real-ip"])
@pytest.mark.parametrize("client", [None, ("", None), ("unix", None), ("unix:/run/a.sock", None)])
def test_remote_ip_uses_forwarding_headers_without_a_peer_address(header, client):
    """A server on a Unix socket gives no peer address: only a process on
    the same machine, such as nginx, can connect to it."""
    value = "for=1.2.3.4" if header == "forwarded" else "1.2.3.4"
    req = _make_request(
        "/", headers=[(header, value), ("x-forwarded-proto", "https")], client=client
    )
    assert req.remote_ip == "1.2.3.4"
    assert req.is_secure is True


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("peer", [
    "127.0.0.1", "127.8.9.10", "::1", "10.1.2.3", "172.16.0.1", "172.31.255.254",
    "192.168.1.1", "169.254.1.1", "fc00::1", "fdab::1", "fe80::1", "::ffff:10.0.0.1",
])
def test_remote_ip_default_trusted_proxies(peer):
    req = _make_request("/", headers=[("x-real-ip", "1.2.3.4")], client=(peer, 5000))
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("peer", ["172.32.0.1", "8.8.8.8", "2001:db8::1", "not-an-ip"])
def test_remote_ip_default_untrusted_peers(peer):
    req = _make_request("/", headers=[("x-real-ip", "1.2.3.4")], client=(peer, 5000))
    assert req.remote_ip == peer


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_skips_trusted_proxies_from_the_right():
    """The client can write anything at the left of the list; the address
    the first untrusted hop connected from is the last it can't fake."""
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", "6.6.6.6, 1.2.3.4 , 10.0.0.2,192.168.0.9")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_all_trusted_is_the_leftmost():
    req = _make_request(
        "/", headers=[("x-forwarded-for", " 10.0.0.3, 10.0.0.2")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "10.0.0.3"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_stops_at_a_value_that_is_not_an_ip():
    req = _make_request(
        "/", headers=[("x-forwarded-for", "1.2.3.4, unknown, 10.0.0.2")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "unknown"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_with_ports_and_ipv6():
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", "6.6.6.6, 2001:db8::7, [fc00::2]:443, 10.0.0.2:8080")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "2001:db8::7"


@pytest.mark.usefixtures("no_current_app")
@pytest.mark.parametrize("hop, expected", [
    # Azure Application Gateway adds the client's port.
    ("203.0.113.5:51234", "203.0.113.5"),
    ("[2001:db8::7]:51234", "2001:db8::7"),
    ("[2001:db8::7]", "2001:db8::7"),
    ("::ffff:203.0.113.5", "203.0.113.5"),
])
def test_remote_ip_x_forwarded_for_without_the_port(hop, expected):
    req = _make_request("/", headers=[("x-forwarded-for", f"{hop}, 10.0.0.2")], client=LOCAL_PROXY)
    assert req.remote_ip == expected


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_skips_trusted_proxies_from_the_right():
    req = _make_request(
        "/",
        headers=[(
            "forwarded",
            'for=6.6.6.6, for=1.2.3.4:4711;proto=https, by=10.0.0.9, '
            'for="[fc00::1]:80", for=10.0.0.2',
        )],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4:4711"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_all_trusted_is_the_leftmost():
    req = _make_request(
        "/", headers=[("forwarded", 'for="[::1]", for=10.0.0.2')], client=LOCAL_PROXY
    )
    assert req.remote_ip == "[::1]"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_obfuscated_identifier():
    req = _make_request(
        "/", headers=[("forwarded", "for=1.2.3.4, for=_hidden")], client=LOCAL_PROXY
    )
    assert req.remote_ip == "_hidden"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_x_forwarded_for_wins_over_forwarded():
    """A proxy that writes only `X-Forwarded-For` (nginx, Caddy, ...) passes a
    `Forwarded` header from the client through untouched."""
    req = _make_request(
        "/",
        headers=[("forwarded", "for=6.6.6.6"), ("x-forwarded-for", "1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_empty_x_forwarded_for_falls_back():
    req = _make_request(
        "/",
        headers=[("x-forwarded-for", " , "), ("forwarded", "for=1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_trusted_peer_without_forwarding_headers():
    req = _make_request("/", client=LOCAL_PROXY)
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_forwarded_without_for_falls_back():
    req = _make_request(
        "/",
        headers=[("forwarded", "proto=https"), ("x-real-ip", "1.2.3.4")],
        client=LOCAL_PROXY,
    )
    assert req.remote_ip == "1.2.3.4"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_without_an_app_uses_the_default_trusted_proxies():
    headers = [("x-forwarded-for", "1.2.3.4")]
    assert _make_request("/", headers=headers, client=LOCAL_PROXY).remote_ip == "1.2.3.4"
    req = _make_request("/", headers=headers, client=("203.0.113.5", 5000))
    assert req.remote_ip == "203.0.113.5"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_custom_trusted_proxies():
    app = App(__name__, {
        "SECRET_KEYS": ["*" * 50],
        "TRUSTED_PROXIES": ["203.0.113.0/24", "2001:db8::1"],
    })
    headers = [("x-forwarded-for", "1.2.3.4, 203.0.113.8")]

    req = _make_request("/", headers=headers, client=("203.0.113.7", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    req = _make_request("/", headers=headers, client=("2001:db8::1", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    # The defaults are replaced, not extended.
    req = _make_request("/", headers=headers, client=LOCAL_PROXY, app=app)
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_no_trusted_proxies():
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "TRUSTED_PROXIES": []})
    req = _make_request(
        "/", headers=[("forwarded", "for=1.2.3.4")], client=LOCAL_PROXY, app=app
    )
    assert req.remote_ip == "127.0.0.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_from_client():
    req = _make_request("/", client=("192.168.1.1", 5000))
    assert req.remote_ip == "192.168.1.1"


@pytest.mark.usefixtures("no_current_app")
def test_remote_ip_no_client():
    req = _make_request("/")
    assert req.remote_ip == ""


@pytest.mark.usefixtures("no_current_app")
def test_trusted_proxies_set_as_strings_after_the_app_was_created():
    """`TRUSTED_PROXIES` is parsed when the app is created; a list of
    strings set later is parsed when it is used."""
    app = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    app.config.TRUSTED_PROXIES = ["203.0.113.0/24"]
    headers = [("x-forwarded-for", "1.2.3.4"), ("x-forwarded-proto", "https")]

    req = _make_request("/", headers=headers, client=("203.0.113.7", 5000), app=app)
    assert req.remote_ip == "1.2.3.4"
    assert req.is_secure is True
    req = _make_request("/", headers=headers, client=LOCAL_PROXY, app=app)
    assert req.remote_ip == "127.0.0.1"
    assert req.is_secure is False


def test_request_id():
    req = _make_request("/", headers=[("x-request-id", "req-123")])
    assert req.request_id == "req-123"


def test_request_id_missing():
    req = _make_request("/")
    assert req.request_id is None


def test_user_agent():
    req = _make_request("/", headers=[("user-agent", "TestBot/1.0")])
    assert req.user_agent == "TestBot/1.0"


def test_user_agent_missing():
    req = _make_request("/")
    assert req.user_agent is None


@pytest.mark.usefixtures("no_current_app")
def test_protocol_from_x_forwarded_proto():
    req = _make_request(
        "http://example.com/", headers=[("x-forwarded-proto", "https")], client=LOCAL_PROXY
    )
    assert req.protocol == "https"
    assert req.is_secure is True


@pytest.mark.usefixtures("no_current_app")
def test_protocol_ignores_x_forwarded_proto_from_an_untrusted_peer():
    req = _make_request(
        "http://example.com/",
        headers=[("x-forwarded-proto", "https")],
        client=("203.0.113.5", 5000),
    )
    assert req.protocol == "http"
    assert req.is_secure is False
    assert req.default_port == 80


@pytest.mark.usefixtures("no_current_app")
def test_protocol_from_x_forwarded_proto_without_a_peer_address():
    """A server on a Unix socket: the peer is a process on the same machine."""
    req = _make_request("http://example.com/", headers=[("x-forwarded-proto", "https")])
    assert req.protocol == "https"
    assert req.is_secure is True
    assert req.default_port == 443


def test_headers_get_missing():
    req = _make_request("/")
    assert req.headers.get("nonexistent") is None


def test_headers_get_string():
    req = _make_request("/")
    req.headers["x-str"] = "string-value"
    assert req.headers.get("x-str") == "string-value"


# --- accept edge cases ---


def test_accept_empty():
    req = _make_request("/")
    assert req.accept == []


def test_accept_quality_sorting():
    req = _make_request(
        "/",
        headers=[
            ("accept", "text/plain;q=0.5,text/html;q=0.9,application/json;q=0.1"),
        ],
    )
    assert req.accept == ["text/html", "text/plain", "application/json"]


def test_accept_default_quality_is_1():
    req = _make_request("/", headers=[("accept", "text/html,text/plain;q=0.5")])
    assert req.accept == ["text/html", "text/plain"]


def test_accept_encoding_empty():
    req = _make_request("/")
    assert req.accept_encoding == []


def test_accept_language_empty():
    req = _make_request("/")
    assert req.accept_language == []


def test_accept_with_quoted_params():
    """Exercise the parse_multivalue slow path (quoted strings)."""
    req = _make_request(
        "/",
        headers=[
            ("accept", 'text/html;level="1",application/json;q=0.5'),
        ],
    )
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "application/json"


def test_accept_with_escaped_quotes():
    """Quoted string with escaped quote inside."""
    req = _make_request(
        "/",
        headers=[
            ("accept", r'text/html;level="foo\"bar",text/plain;q=0.5'),
        ],
    )
    assert req.accept[0] == "text/html"
    assert req.accept[1] == "text/plain"


@pytest.mark.parametrize("header, expected", [
    # A parameter without a value is ignored, with or without quotes.
    ("text/html;level,application/json;q=0.5", ["text/html", "application/json"]),
    ('text/html;level,application/json;q="0.5"', ["text/html", "application/json"]),
    # An empty parameter, as after a trailing `;`.
    ("text/html;,application/json;q=0.5", ["text/html", "application/json"]),
    ("application/json;q=0.5,text/html;", ["text/html", "application/json"]),
    # A `q` that isn't a number from 0 to 1 is ignored: the weight is 1.
    ("application/json;q=0.5,text/html;q=abc", ["text/html", "application/json"]),
    ('application/json;q=0.5,text/html;q="abc"', ["text/html", "application/json"]),
    ("application/json;q=0.5,text/html;q=", ["text/html", "application/json"]),
    ("application/json;q=0.5,text/html;q=nan", ["text/html", "application/json"]),
    # A q over 1 counts as 1: a tie, so the order in the header stays.
    ("application/json,text/html;q=2", ["application/json", "text/html"]),
    ("text/html;q=-1,application/json;q=0.5", ["text/html", "application/json"]),
])
def test_accept_malformed_parameters_are_ignored(header, expected):
    req = _make_request("/", headers=[("accept", header)])
    assert req.accept == expected


def test_accept_language_malformed_q_is_ignored():
    req = _make_request("/", headers=[("accept-language", "fr;q=0.5,en-US;q=x")])
    assert req.accept_language == ["en_US", "fr"]


def test_accept_semicolon_without_equals():
    """Semicolon-separated attribute without =value (slow path)."""
    req = _make_request(
        "/",
        headers=[
            ("accept", '"text/html";level'),
        ],
    )
    # Should still parse without error
    assert len(req.accept) >= 1


# --- if_none_match edge cases ---


def test_if_none_match_empty():
    req = _make_request("/")
    assert req.if_none_match == []


def test_if_none_match_single():
    req = _make_request("/", headers=[("if-none-match", '"etag1"')])
    assert req.if_none_match == ['"etag1"']


def test_if_none_match_whitespace():
    req = _make_request("/", headers=[("if-none-match", '"a", "b"')])
    assert '"a"' in req.if_none_match
    assert '"b"' in req.if_none_match


# --- cookie edge cases ---


def test_cookies_empty_header():
    req = _make_request("/")
    assert req.cookies == {}


def test_cookies_empty_name():
    """Cookie chunk without '=' gets empty name."""
    req = _make_request("/", headers=[("cookie", "justvalue")])
    assert req.cookies[""] == "justvalue"


def test_cookies_quoted_value():
    req = _make_request("/", headers=[("cookie", 'a="quoted"')])
    assert req.cookies["a"] == "quoted"


def test_cookies_empty_pair_skipped():
    req = _make_request("/", headers=[("cookie", "a=1;  ;b=2")])
    assert req.cookies["a"] == "1"
    assert req.cookies["b"] == "2"


# --- host parsing ---


def test_server_none_fallback_to_host_header():
    req = Request(headers=[("host", "example.com:8080")])
    assert req.host == "example.com"
    assert req.port == 8080


def test_allow_no_host():
    req = Request()
    assert req.host == ""


def test_host_from_header_ipv6():
    req = Request(headers=[("host", "[::1]")])
    assert req.host == "::1"
    assert req.port == 80  # default


def test_host_from_header_ipv6_with_port():
    req = Request(headers=[("host", "[::1]:9090")])
    assert req.host == "::1"
    assert req.port == 9090


def test_host_from_header_non_decimal_port():
    # A non-numeric port is invalid per RFC 9112 §3.2 / RFC 3986 §3.2.3.
    with pytest.raises(InvalidHeader, match="Host"):
        Request(headers=[("host", "example.com:abc")])


def test_host_from_header_simple():
    req = Request(headers=[("host", "myhost:8080")])
    assert req.host == "myhost"
    assert req.port == 8080


@pytest.mark.parametrize("value", [
    "example.com",
    "example.com:8080",
    "example.com:",  # empty port is allowed by RFC 3986 (port = *DIGIT)
    "sub.example.com",
    "localhost",
    "something.localhost:1234",
    "127.0.0.1",
    "127.0.0.1:5000",
    "[::1]",
    "[::1]:9090",
    "[2001:db8::1]:443",
    "my-host_1.example~test",  # unreserved chars
    "xn--80ak6aa92e.com",  # punycode (IDN)
])
def test_accepts_valid_host(value):
    host, _ = parse_host(value)
    print(value)
    assert host is not None


@pytest.mark.parametrize("value", [
    "example.com/abc?bar=",  # X41-2026-002: path/query injection
    "example.com/abc",
    "example.com?x=1",
    "example.com#frag",
    "user@example.com",  # userinfo is not part of a Host header
    "example.com:abc",  # non-numeric port
    "exa mple.com",  # space
    "example.com\n",  # trailing newline (header injection)
    "exam\tple.com",  # control character
    "::1",  # unbracketed IPv6
    "",  # empty
])
def test_rejects_invalid_host(value):
    with pytest.raises(InvalidHeader, match="Host"):
        print(value)
        host, _ = parse_host(value)


# --- request_id edge cases ---


def test_request_id_truncated():
    long_id = "a" * 300
    req = _make_request("/", headers=[("x-request-id", long_id)])
    assert req.request_id and len(req.request_id) == 200


def test_request_id_non_ascii_removed():
    req = _make_request("/", headers=[("x-request-id", "abc\x80\x81def")])
    assert req.request_id == "abcdef"


# --- forwarded edge cases ---


def test_forwarded_empty():
    req = _make_request("/")
    assert req.forwarded == []


def test_forwarded_multiple_proxies():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4,for=5.6.7.8"),
        ],
    )
    assert len(req.forwarded) == 2
    assert req.forwarded[0]["for"] == "1.2.3.4"
    assert req.forwarded[1]["for"] == "5.6.7.8"


def test_forwarded_quoted_values():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", 'for="1.2.3.4"'),
        ],
    )
    assert req.forwarded[0]["for"] == "1.2.3.4"


def test_forwarded_escaped_quotes():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", r'for="val\"ue"'),
        ],
    )
    assert req.forwarded[0]["for"] == 'val"ue'


def test_forwarded_port_suffix():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4:8080"),
        ],
    )
    assert req.forwarded[0]["for"] == "1.2.3.4:8080"


def test_forwarded_multiple_params():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4;proto=https;by=proxy"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"
    assert fwd["by"] == "proxy"


def test_forwarded_case_insensitive_keys():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "For=1.2.3.4;Proto=https"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"


def test_forwarded_whitespace_between_pairs():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4 ; proto=https"),
        ],
    )
    fwd = req.forwarded[0]
    assert fwd["for"] == "1.2.3.4"
    assert fwd["proto"] == "https"


def test_forwarded_bad_syntax_skipped():
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "!!!,for=1.2.3.4"),
        ],
    )
    # First proxy is empty (bad syntax skipped), second has the value
    assert req.forwarded[1]["for"] == "1.2.3.4"


def test_forwarded_bad_syntax_after_valid():
    """Two valid pairs without separator → bad syntax, skip to next comma."""
    req = _make_request(
        "/",
        headers=[
            ("forwarded", "for=1.2.3.4 for=bad,for=5.6.7.8"),
        ],
    )
    # After first valid pair, "for=bad" is encountered without separator
    # so it skips to comma, then parses for=5.6.7.8
    assert req.forwarded[0]["for"] == "1.2.3.4"
    assert req.forwarded[1]["for"] == "5.6.7.8"
