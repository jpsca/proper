import warnings

import pytest

from proper import Response
from proper import status as pstatus
from proper.core.response.cookies import (
    HOST_PREFIX,
    SECURE_PREFIX,
    validate_cookie_size,
    validate_domain,
)
from proper.helpers.asgi import make_test_scope


def _make_response(*, status=pstatus.ok, **scope_kw):
    """Build a Response with a valid ASGI scope."""
    scope = make_test_scope(**scope_kw)
    response = Response(scope, status=status)
    return response


def test_no_cookies():
    resp = _make_response()
    assert not resp.cookies


def test_set_minimal_cookie():
    resp = _make_response()
    resp.set_cookie("foo", "bar")
    assert resp.cookies["foo"].value == "bar"
    assert resp.cookies["foo"]["path"] == "/"
    assert resp.cookies["foo"]["samesite"] == "Lax"


def test_cookie_tuples_single():
    resp = _make_response()
    resp.set_cookie("foo", "bar")
    tuples = resp.get_cookie_tuples()
    assert len(tuples) == 1
    assert tuples[0][0] == "Set-Cookie"
    assert "foo=bar" in tuples[0][1]


def test_invalid_samesite():
    resp = _make_response()
    with pytest.raises(ValueError):
        resp.set_cookie("foo", "bar", samesite="invalid") # type: ignore


def test_cookie_no_path():
    resp = _make_response()
    resp.set_cookie("foo", "bar", path="")
    headers = resp.get_headers_list()
    cookie_header = [h for h in headers if h[0] == "Set-Cookie"][0][1]
    assert "foo=bar" in cookie_header


def test_cookie_max_age():
    resp = _make_response()
    resp.set_cookie("foo", "bar", max_age=3600)
    assert resp.cookies["foo"]["max-age"] == 3600
    assert resp.cookies["foo"]["expires"]


def test_cookie_domain():
    resp = _make_response()
    resp.set_cookie("foo", "bar", domain="example.com")
    assert resp.cookies["foo"]["domain"] == "example.com"


def test_cookie_secure():
    resp = _make_response()
    resp.set_cookie("foo", "bar", secure=True)
    assert resp.cookies["foo"]["secure"]


def test_cookie_httponly():
    resp = _make_response()
    resp.set_cookie("foo", "bar", httponly=True)
    assert resp.cookies["foo"]["httponly"]


def test_cookie_samesite_strict():
    resp = _make_response()
    resp.set_cookie("foo", "bar", samesite="Strict")
    assert resp.cookies["foo"]["samesite"] == "Strict"


def test_cookie_samesite_none():
    resp = _make_response()
    resp.set_cookie("foo", "bar", samesite=None)
    assert resp.cookies["foo"]["samesite"] == ""


def test_cookie_comment():
    resp = _make_response()
    resp.set_cookie("foo", "bar", comment="test comment")
    assert resp.cookies["foo"]["comment"] == "test comment"


def test_cookie_integer_value():
    resp = _make_response()
    resp.set_cookie("count", 42)
    assert resp.cookies["count"].value == "42"


def test_cookie_bytes_value():
    resp = _make_response()
    resp.set_cookie("data", b"hello")
    assert resp.cookies["data"].value == "hello"


def test_filter_cookie_name():
    resp = _make_response()
    resp.set_cookie("fo,o=!", "bar")
    assert "foo!" in resp.cookies


def test_host_prefix_forces_path():
    resp = _make_response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "val", path="/admin")
    assert resp.cookies[key]["path"] == "/"


def test_host_prefix_no_domain():
    resp = _make_response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "val", domain="example.com")
    assert not resp.cookies[key]["domain"]


def test_host_prefix_secure():
    resp = _make_response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "val")
    assert resp.cookies[key]["secure"]


def test_secure_prefix_secure():
    resp = _make_response()
    key = SECURE_PREFIX + "mycookie"
    resp.set_cookie(key, "val")
    assert resp.cookies[key]["secure"]


def test_unset_cookie():
    resp = _make_response()
    resp.unset_cookie("foo")
    assert resp.cookies["foo"].value == " "
    assert resp.cookies["foo"]["max-age"] == 0


def test_set_same_cookie_overwrites():
    resp = _make_response()
    resp.set_cookie("foo", "bar1")
    resp.set_cookie("foo", "bar2")
    assert len(resp.cookies) == 1
    assert resp.cookies["foo"].value == "bar2"


def test_set_several_cookies():
    resp = _make_response()
    resp.set_cookie("foo", "bar")
    resp.set_cookie("baz", "qux")
    headers = resp.get_headers_list()
    cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
    assert len(cookie_headers) == 2


def test_disable_cookies():
    resp = _make_response()
    resp.set_cookie("foo", "bar")
    resp.disable_cookies = True
    assert resp.get_cookie_tuples() == []


def test_warn_for_big_cookie():
    resp = _make_response()
    with pytest.warns(UserWarning, match="too large"):
        resp.set_cookie("foo", "a" * 4093)


def test_warn_for_localhost_domain():
    resp = _make_response()
    with pytest.warns(UserWarning, match="localhost"):
        resp.set_cookie("foo", "bar", domain="localhost")


def test_max_cookie_size_zero_skips_validation():
    resp = _make_response()
    resp.max_cookie_size = 0
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        resp.set_cookie("foo", "a" * 5000)


def test_no_cookies_empty_tuples():
    resp = _make_response()
    assert resp.get_cookie_tuples() == []


def test_valid_domain():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_domain("example.com")


def test_none_domain():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_domain(None)


def test_localhost_warns():
    with pytest.warns(UserWarning, match="localhost"):
        validate_domain("localhost")


def test_empty_string():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_domain("")


def test_within_limit():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        validate_cookie_size("foo", "short", 100)


def test_exceeds_limit():
    with pytest.warns(UserWarning, match="too large"):
        validate_cookie_size("foo", "x" * 200, 100)


def test_warning_contains_sizes():
    with pytest.warns(UserWarning, match="200 bytes") as record:
        validate_cookie_size("foo", "x" * 200, 100)
    assert "100 bytes" in str(record[0].message)
