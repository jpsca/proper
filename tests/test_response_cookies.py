import pytest

from proper.response import Response
from proper.helpers.cookies import HOST_PREFIX, SECURE_PREFIX


def set_no_cookies():
    resp = Response()

    assert not resp.cookies


def test_set_minimal_cookie():
    resp = Response()
    resp.set_cookie("foo", "bar")

    assert resp.cookies["foo"].value == "bar"
    assert resp.headers_items[-1] == ("Set-Cookie", "foo=bar; Path=/")
    assert resp.cookies["foo"]["path"] == "/"
    assert not resp.cookies["foo"]["domain"]
    assert not resp.cookies["foo"]["secure"]
    assert not resp.cookies["foo"]["httponly"]
    assert not resp.cookies["foo"]["comment"]
    assert not resp.cookies["foo"]["samesite"]


def test_set_minimal_cookie_no_path():
    resp = Response()
    resp.set_cookie("foo", "bar", path=None)

    assert resp.headers_items[-1] == ("Set-Cookie", "foo=bar")


def test_set_several_cookies():
    resp = Response()
    resp.set_cookie("foo", "bar")
    resp.set_cookie("lorem", "ipsum")

    assert resp.cookies["foo"].value == "bar"
    assert resp.headers_items[-2:] == [
        ("Set-Cookie", "foo=bar; Path=/"),
        ("Set-Cookie", "lorem=ipsum; Path=/"),
    ]


def test_warn_for_big_cookie():
    resp = Response()
    with pytest.warns(UserWarning):
        resp.set_cookie("foo", "a" * 4093)


def test_warn_for_localhost():
    resp = Response()
    with pytest.warns(UserWarning):
        resp.set_cookie("foo", "a", domain="localhost")


def test_filter_cookie_name():
    resp = Response()
    resp.set_cookie("fo,o=!", "bar")

    assert "foo!" in resp.cookies


def test_cookie_max_age():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", max_age=100)

    assert resp.cookies["lorem"]["max-age"] == 100
    assert resp.cookies["lorem"]["expires"]
    header_value = resp.headers_items[-1][1]
    assert "lorem=ipsum" in header_value
    assert "; Max-Age=100" in header_value
    assert "; expires=" in header_value


def test_cookie_path():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", path="/admin")

    assert resp.cookies["lorem"]["path"] == "/admin"
    assert resp.headers_items[-1][1] == "lorem=ipsum; Path=/admin"


def test_cookie_domain():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", domain="subdomain.example.com")

    assert resp.cookies["lorem"]["domain"] == "subdomain.example.com"
    assert "; Domain=subdomain.example.com" in resp.headers_items[-1][1]


def test_cookie_secure():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", secure=True)

    assert resp.cookies["lorem"]["secure"]
    assert "; Secure" in resp.headers_items[-1][1]


def test_cookie_httponly():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", httponly=True)

    assert resp.cookies["lorem"]["httponly"]
    assert "; HttpOnly" in resp.headers_items[-1][1]


@pytest.mark.parametrize("samesite", ["lax", "strict"])
def test_cookie_samesite(samesite):
    resp = Response()
    resp.set_cookie("lorem", "ipsum", samesite=samesite)

    assert resp.cookies["lorem"]["samesite"] == samesite
    assert samesite in resp.headers_items[-1][1]


def test_cookie_invalid_samesite():
    resp = Response()
    with pytest.raises(ValueError):
        resp.set_cookie("lorem", "ipsum", samesite="whatever")


def test_cookie_comment():
    resp = Response()
    resp.set_cookie("lorem", "ipsum", comment="This is cool")

    assert resp.cookies["lorem"]["comment"] == "This is cool"
    assert '; Comment="This is cool"' in resp.headers_items[-1][1]


def test_cookie_host_prefix_path():
    resp = Response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "ipsum", path="/admin")

    assert resp.cookies[key]["path"] == "/"


def test_cookie_host_prefix_domain():
    resp = Response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "ipsum", domain="subdomain.example.com")

    assert not resp.cookies[key]["domain"]


def test_cookie_host_prefix_secure():
    resp = Response()
    key = HOST_PREFIX + "mycookie"
    resp.set_cookie(key, "ipsum")

    assert resp.cookies[key]["secure"]


def test_cookie_secure_prefix_secure():
    resp = Response()
    key = SECURE_PREFIX + "mycookie"
    resp.set_cookie(key, "ipsum")

    assert resp.cookies[key]["secure"]


def test_unset_cookie():
    resp = Response()
    resp.set_cookie("foo", "bar")
    resp.unset_cookie("foo")

    assert "foo" not in resp.cookies


def test_unset_not_set_cookie():
    resp = Response()
    resp.unset_cookie("foo")

    assert "foo" not in resp.cookies


def test_delete_cookie():
    resp = Response()
    resp.delete_cookie("foo")

    assert not resp.cookies["foo"].value
    assert resp.cookies["foo"]["max-age"] == 0


def test_set_same_cookie():
    resp = Response()
    resp.set_cookie("foo", "bar1", path=None)
    resp.set_cookie("foo", "bar2", path=None)

    assert len(resp.cookies) == 1
    assert resp.cookies["foo"].value == "bar2"
