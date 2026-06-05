from unittest.mock import patch

from proper.constants import SIGNED_COOKIE_SALT
from proper.core.request import Request
from proper.helpers import DotDict, MultiDict
from proper.helpers.asgi import make_test_scope


def _make_request(url="/", method="GET", **kw):
    scope = make_test_scope(url, method=method, **kw)
    return Request(scope)


def test_test_scope_defaults():
    scope = make_test_scope()
    assert scope["type"] == "http"
    assert scope["method"] == "GET"
    assert scope["path"] == "/"
    assert scope["scheme"] == "http"
    assert scope["server"] == ("example.com", 80)
    assert scope["http_version"] == "1.1"


def test_test_scope_full_url():
    scope = make_test_scope("http://myhost:9090/hello?x=1")
    assert scope["server"] == ("myhost", 9090)
    assert scope["path"] == "/hello"
    assert scope["query_string"] == b"x=1"


def test_test_scope_https_default_port():
    scope = make_test_scope("https://secure.example.com/path")
    assert scope["scheme"] == "https"
    assert scope["server"] == ("secure.example.com", 443)


def test_test_scope_params_override_query():
    scope = make_test_scope("/search?old=1", params={"q": "test"})
    assert scope["query_string"] == b"q=test"


def test_test_scope_custom_method():
    scope = make_test_scope("/", method="post")
    assert scope["method"] == "POST"


def test_test_scope_custom_scope_type():
    scope = make_test_scope("/", scope_type="websocket")
    assert scope["type"] == "websocket"


def test_test_scope_extra_kwargs():
    scope = make_test_scope("/", client=("127.0.0.1", 12345))
    assert scope["client"] == ("127.0.0.1", 12345)


def test_test_scope_custom_headers():
    scope = make_test_scope(
        "/",
        headers=[("x-custom", "value"), (b"x-binary", b"bval")],
    )
    header_names = [name for name, _ in scope["headers"]]
    assert b"x-custom" in header_names
    assert b"x-binary" in header_names


def test_test_scope_path_only_url():
    scope = make_test_scope("/foo/bar")
    assert scope["path"] == "/foo/bar"
    assert scope["server"] == ("example.com", 80)


def test_repr():
    req = _make_request("/hello", method="GET")
    r = repr(req)
    assert "GET" in r
    assert "/hello" in r


def test_app(app):
    scope = make_test_scope("/")
    scope["app"] = app
    req = Request(scope)
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
    scope = make_test_scope("http://example.com/search?q=test&page=2")
    scope["app"] = app
    req = Request(scope)
    assert req.query.get("q") == "test"
    assert req.query.get("page") == "2"


def test_query_cached(app):
    scope = make_test_scope("http://example.com/?x=1")
    scope["app"] = app
    req = Request(scope)
    q1 = req.query
    q2 = req.query
    assert q1 is q2


def test_query_string():
    req = _make_request("http://example.com/path?a=1&b=2")
    assert req.query_string == "a=1&b=2"


def test_query_string_bytes():
    scope = make_test_scope("/")
    scope["query_string"] = b"key=val"
    req = Request(scope)
    assert req.query_string == "key=val"


def test_query_string_str():
    scope = make_test_scope("/")
    scope["query_string"] = "key=val"
    req = Request(scope)
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
    scope = make_test_scope("/")
    scope["app"] = app
    scope["headers"].append((b"cookie", f"test={signed_value}".encode()))
    req = Request(scope)
    assert req.get_signed_cookie("test") == "secret_data"


def test_get_signed_cookie_missing(app):
    scope = make_test_scope("/")
    scope["app"] = app
    req = Request(scope)
    assert req.get_signed_cookie("missing") is None
    assert req.get_signed_cookie("missing", "default") == "default"


def test_get_signed_cookie_bad_signature(app):
    scope = make_test_scope("/")
    scope["app"] = app
    scope["headers"].append((b"cookie", b"test=tampered_value"))
    req = Request(scope)
    assert req.get_signed_cookie("test") is None
    assert req.get_signed_cookie("test", "fallback") == "fallback"


def test_get_signed_cookie_bytes_value(app):
    signed_value = app.dumps("bytes_test")
    scope = make_test_scope("/")
    scope["app"] = app
    scope["headers"].append((b"cookie", f"test={signed_value}".encode()))
    req = Request(scope)
    # Patch loads to return bytes
    with patch.object(type(app), "loads", return_value=b"decoded_bytes"):
        result = req.get_signed_cookie("test")
        assert result == "decoded_bytes"
