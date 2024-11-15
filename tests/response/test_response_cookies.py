import pytest

from proper.response import Response
from proper.response.cookies import HOST_PREFIX, SECURE_PREFIX


def set_no_cookies():
    response = Response()

    assert not response.cookies


def test_set_minimal_cookie():
    response = Response()
    response.set_cookie("foo", "bar")

    assert response.cookies["foo"].value == "bar"
    assert response._get_cookie_tuples() == [("Set-Cookie", "foo=bar; Path=/; SameSite=Lax")]
    assert response.cookies["foo"]["path"] == "/"
    assert response.cookies["foo"]["samesite"] == "Lax"
    assert not response.cookies["foo"]["domain"]
    assert not response.cookies["foo"]["secure"]
    assert not response.cookies["foo"]["httponly"]
    assert not response.cookies["foo"]["comment"]


def test_invalid_samesite():
    response = Response()
    with pytest.raises(ValueError):
        response.set_cookie("foo", "bar", samesite="lol")  # type: ignore


def test_set_minimal_cookie_no_path():
    response = Response()
    response.set_cookie("foo", "bar", path=None)  # type: ignore
    headers_list = response.get_headers_list()

    assert headers_list[-1] == ("Set-Cookie", "foo=bar; SameSite=Lax")


def test_set_several_cookies():
    response = Response()
    response.set_cookie("foo", "bar")
    response.set_cookie("lorem", "ipsum")
    headers_list = response.get_headers_list()

    assert response.cookies["foo"].value == "bar"
    print(headers_list[-2:])
    assert headers_list[-1] == (
        "Set-Cookie", "foo=bar; Path=/; SameSite=Lax, lorem=ipsum; Path=/; SameSite=Lax"
    )


def test_warn_for_big_cookie():
    response = Response()
    with pytest.warns(UserWarning):
        response.set_cookie("foo", "a" * 4093)


def test_warn_for_localhost():
    response = Response()
    with pytest.warns(UserWarning):
        response.set_cookie("foo", "a", domain="localhost")


def test_filter_cookie_name():
    response = Response()
    response.set_cookie("fo,o=!", "bar")

    assert "foo!" in response.cookies


def test_cookie_max_age():
    response = Response()
    response.set_cookie("lorem", "ipsum", max_age=100)
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["max-age"] == 100
    assert response.cookies["lorem"]["expires"]

    header_value = headers_list[-1][1]
    assert "lorem=ipsum" in header_value
    assert "; Max-Age=100" in header_value
    assert "; expires=" in header_value


def test_cookie_path():
    response = Response()
    response.set_cookie("lorem", "ipsum", path="/admin")
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["path"] == "/admin"
    assert headers_list[-1][1] == "lorem=ipsum; Path=/admin; SameSite=Lax"


def test_cookie_domain():
    response = Response()
    response.set_cookie("lorem", "ipsum", domain="subdomain.example.com")
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["domain"] == "subdomain.example.com"
    assert "; Domain=subdomain.example.com" in headers_list[-1][1]


def test_cookie_secure():
    response = Response()
    response.set_cookie("lorem", "ipsum", secure=True)
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["secure"]
    assert "; Secure" in headers_list[-1][1]


def test_cookie_httponly():
    response = Response()
    response.set_cookie("lorem", "ipsum", httponly=True)
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["httponly"]
    assert "; HttpOnly" in headers_list[-1][1]


@pytest.mark.parametrize("samesite", ["lax", "strict"])
def test_cookie_samesite(samesite):
    response = Response()
    response.set_cookie("lorem", "ipsum", samesite=samesite)
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["samesite"] == samesite
    assert samesite in headers_list[-1][1]


def test_cookie_invalid_samesite():
    response = Response()
    with pytest.raises(ValueError):
        response.set_cookie("lorem", "ipsum", samesite="whatever")


def test_cookie_comment():
    response = Response()
    response.set_cookie("lorem", "ipsum", comment="This is cool")
    headers_list = response.get_headers_list()

    assert response.cookies["lorem"]["comment"] == "This is cool"
    assert '; Comment="This is cool"' in headers_list[-1][1]


def test_cookie_host_prefix_path():
    response = Response()
    key = HOST_PREFIX + "mycookie"
    response.set_cookie(key, "ipsum", path="/admin")

    assert response.cookies[key]["path"] == "/"


def test_cookie_host_prefix_domain():
    response = Response()
    key = HOST_PREFIX + "mycookie"
    response.set_cookie(key, "ipsum", domain="subdomain.example.com")

    assert not response.cookies[key]["domain"]


def test_cookie_host_prefix_secure():
    response = Response()
    key = HOST_PREFIX + "mycookie"
    response.set_cookie(key, "ipsum")

    assert response.cookies[key]["secure"]


def test_cookie_secure_prefix_secure():
    response = Response()
    key = SECURE_PREFIX + "mycookie"
    response.set_cookie(key, "ipsum")

    assert response.cookies[key]["secure"]


def test_unset_cookie():
    response = Response()
    response.unset_cookie("foo")

    assert not response.cookies["foo"].value
    assert response.cookies["foo"]["max-age"] == 0


def test_set_same_cookie():
    response = Response()
    response.set_cookie("foo", "bar1", path=None)  # type: ignore
    response.set_cookie("foo", "bar2", path=None)  # type: ignore

    assert len(response.cookies) == 1
    assert response.cookies["foo"].value == "bar2"
