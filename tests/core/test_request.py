from unittest.mock import patch

from proper.constants import SIGNED_COOKIE_SALT
from proper.core.request import Request
from proper.helpers import DotDict, MultiDict
from proper.test_client import make_test_request


def _make_request(url="/", method="GET", **kw):
    return make_test_request(url, method=method, **kw)


def test_test_request_defaults():
    req = make_test_request()
    assert req.method == "GET"
    assert req.path == "/"
    assert req.scheme == "http"
    assert req.server == ("example.com", 80)
    assert req.http_version == "1.1"
    assert req.headers.get("host") == "example.com"


def test_test_request_full_url():
    req = make_test_request("http://myhost:9090/hello?x=1")
    assert req.server == ("myhost", 9090)
    assert req.path == "/hello"
    assert req.query_string == "x=1"
    assert req.headers.get("host") == "myhost:9090"


def test_test_request_https_default_port():
    req = make_test_request("https://secure.example.com/path")
    assert req.scheme == "https"
    assert req.server == ("secure.example.com", 443)


def test_test_request_params_override_query():
    req = make_test_request("/search?old=1", params={"q": "test"})
    assert req.query_string == "q=test"


def test_test_request_custom_method():
    req = make_test_request("/", method="post")
    assert req.method == "POST"


def test_test_request_client():
    req = make_test_request("/", client=("127.0.0.1", 12345))
    assert req.client == ("127.0.0.1", 12345)


def test_test_request_custom_headers():
    req = make_test_request("/", headers=[("x-custom", "value"), ("x-other", "o")])
    assert req.headers.get("x-custom") == "value"
    assert req.headers.get("x-other") == "o"


def test_test_request_headers_mapping():
    req = make_test_request("/", headers={"x-custom": "value", "host": "given.test"})
    assert req.headers.get("x-custom") == "value"
    assert req.headers.get("host") == "given.test"


def test_test_request_path_only_url():
    req = make_test_request("/foo/bar")
    assert req.path == "/foo/bar"
    assert req.server == ("example.com", 80)


def test_repr():
    req = _make_request("/hello", method="GET")
    r = repr(req)
    assert "GET" in r
    assert "/hello" in r


def test_app(app):
    req = make_test_request("/", app=app)
    assert req.app is app


def test_session_default():
    req = _make_request("/")
    assert isinstance(req.session, DotDict)
    assert len(req.session) == 0


def test_session_setter():
    req = _make_request("/")
    req.session = {"key": "val"}
    assert isinstance(req.session, DotDict)
    assert req.session.key == "val"


def test_http_version():
    req = _make_request("/")
    assert req.http_version == "1.1"


def test_flashes_empty():
    req = _make_request("/")
    assert req.flashes == []


def test_flashes_from_session():
    req = _make_request("/")
    req.session = {"_flashes": [("info", "hello")]}
    assert req.flashes == [("info", "hello")]


def test_query(app):
    req = make_test_request("http://example.com/search?q=test&page=2", app=app)
    assert req.query.get("q") == "test"
    assert req.query.get("page") == "2"


def test_query_cached(app):
    req = make_test_request("http://example.com/?x=1", app=app)
    q1 = req.query
    q2 = req.query
    assert q1 is q2


def test_query_string():
    req = _make_request("http://example.com/path?a=1&b=2")
    assert req.query_string == "a=1&b=2"


def test_query_string_bytes():
    req = Request(query_string="key=val")
    assert req.query_string == "key=val"


def test_query_string_str():
    req = Request(query_string="key=val")
    assert req.query_string == "key=val"


def test_query_string_empty():
    req = _make_request("/")
    assert req.query_string == ""


def test_url():
    req = _make_request("http://example.com/path?q=1")
    assert req.url == "/path?q=1"


def test_get_url_without_query():
    req = _make_request("http://example.com/path?q=1")
    assert req.get_url(include_query=False) == "/path"


def test_get_url_no_query_string():
    req = _make_request("http://example.com/path")
    assert req.get_url() == "/path"


def test_form_default():
    req = _make_request("/")
    assert isinstance(req.form, MultiDict)
    assert len(req.form) == 0


def test_matched_defaults():
    req = _make_request("/")
    assert not req.matched_route
    assert not req.matched_params
    assert not req.matched_action


def test_get_cookie():
    req = _make_request("/", headers=[("cookie", "name=Jon")])
    assert req.get_cookie("name") == "Jon"


def test_get_cookie_default():
    req = _make_request("/")
    assert req.get_cookie("missing") is None
    assert req.get_cookie("missing", "fallback") == "fallback"


def test_get_signed_cookie(app):
    signed_value = app.dumps("secret_data", SIGNED_COOKIE_SALT)
    req = make_test_request("/", app=app, headers=[("cookie", f"test={signed_value}")])
    assert req.get_signed_cookie("test") == "secret_data"


def test_get_signed_cookie_missing(app):
    req = make_test_request("/", app=app)
    assert req.get_signed_cookie("missing") is None
    assert req.get_signed_cookie("missing", "default") == "default"


def test_get_signed_cookie_bad_signature(app):
    req = make_test_request("/", app=app, headers=[("cookie", "test=tampered_value")])
    assert req.get_signed_cookie("test") is None
    assert req.get_signed_cookie("test", "fallback") == "fallback"


def test_get_signed_cookie_bytes_value(app):
    signed_value = app.dumps("bytes_test")
    req = make_test_request("/", app=app, headers=[("cookie", f"test={signed_value}")])
    # Patch loads to return bytes
    with patch.object(type(app), "loads", return_value=b"decoded_bytes"):
        result = req.get_signed_cookie("test")
        assert result == "decoded_bytes"
