import pytest

from proper.constants import (
    DELETE,
    FLASHES_SESSION_KEY,
    GET,
    HEAD,
    OPTIONS,
    PATCH,
    POST,
    PUT,
)
from proper.errors import InvalidHeader
from proper.helpers import Dot
from proper.request import Request


def test_query():
    req = Request(QUERY_STRING="foo=bar&ok&color=red&color=green&color=blue")

    assert req.query
    assert req.query == req.query  # idempotent
    assert req.query.get("foo") == "bar"
    assert req.query.get("ok") is True
    assert req.query.getall("color") == ["red", "green", "blue"]


def test_empty_body():
    req = Request()

    assert req.form is not None
    assert not req.form
    assert req.form == req.form  # idempotent


def test_no_content_length():
    req = Request()
    assert req.content_length == 0


def test_content_length():
    req = Request(CONTENT_LENGTH="456789")
    assert req.content_length == 456_789
    assert req.content_length == req.content_length


def test_invalid_content_length():
    req = Request(CONTENT_LENGTH="very large")
    with pytest.raises(InvalidHeader):
        assert req.content_length


def test_negative_content_length():
    req = Request(CONTENT_LENGTH="-456789")
    with pytest.raises(InvalidHeader):
        assert req.content_length


def test_extra_content_length():
    req = Request(CONTENT_LENGTH="3434 or something")
    with pytest.raises(InvalidHeader):
        assert req.content_length


def test_parse_host():
    req = Request(HTTP_HOST="0.0.0.0")
    assert req.host == "0.0.0.0"
    assert req.port == 80

    req = Request(HTTP_HOST="0.0.0.0:5000")
    assert req.host == "0.0.0.0"
    assert req.port == 5000

    req = Request(HTTP_HOST="localhost")
    assert req.host == "localhost"
    assert req.port == 80

    ipv6_addr = "2800:200:e480:10d4:dc9e:51f0:f99e:b5f4"
    req = Request(HTTP_HOST="[" + ipv6_addr + "]")
    assert req.host == ipv6_addr
    assert req.port == 80

    req = Request(HTTP_HOST="[" + ipv6_addr + "]:34567")
    assert req.host == ipv6_addr
    assert req.port == 34567

    req = Request(HTTP_HOST="example.com")
    assert req.host == "example.com"
    assert req.port == 80

    req = Request(HTTP_HOST="proper.jpscaletti.com")
    assert req.host == "proper.jpscaletti.com"
    assert req.port == 80

    req = Request(HTTP_HOST="proper.jpscaletti.com:4000")
    assert req.host == "proper.jpscaletti.com"
    assert req.port == 4000

    req = Request(HTTP_HOST="example.com", HTTP_X_FORWARDED_PROTO="https")
    assert req.host == "example.com"
    assert req.port == 443


def test_host_with_port():
    req = Request(HTTP_HOST="example.com")
    assert req.host_with_port == "example.com"

    req = Request(HTTP_HOST="example.com:80")
    assert req.host_with_port == "example.com"

    req = Request(HTTP_HOST="example.com:5000")
    assert req.host_with_port == "example.com:5000"

    req = Request(HTTP_HOST="example.com:443")
    assert req.host_with_port == "example.com:443"

    req = Request(HTTP_HOST="example.com:443", HTTP_X_FORWARDED_PROTO="https")
    assert req.host_with_port == "example.com"


def test_no_remote_addr_is_127_0_0_1():
    req = Request()
    if "REMOTE_ADDR" in req.environ:
        del req.environ["REMOTE_ADDR"]
    assert req.remote_addr == "127.0.0.1"


def test_remote_addr():
    req = Request(REMOTE_ADDR="192.168.56.1")
    assert req.remote_addr == req.remote_addr == "192.168.56.1"


def test_x_remote_addr():
    req = Request(HTTP_X_REAL_IP="172.217.15.206", REMOTE_ADDR="localhost")
    assert req.remote_addr == req.remote_addr == "172.217.15.206"


def test_no_cookies():
    req = Request()

    assert req.cookies == req.cookies
    assert not req.cookies


def test_cookies():
    header = "logged_in=yes; _octo=GH1.1.19797273.434; has_recent_activity=1;"
    req = Request(HTTP_COOKIE=header)

    assert req.cookies == req.cookies
    assert req.cookies["logged_in"] == "yes"
    assert req.cookies["_octo"] == "GH1.1.19797273.434"
    assert req.cookies["has_recent_activity"] == "1"


def test_parse_one_value():
    header = "dismiss=6"
    req = Request(HTTP_COOKIE=header)

    assert req.cookies["dismiss"] == "6"


def test_parse_invalid_cookies():
    header = "this is not a cookie"
    req = Request(HTTP_COOKIE=header)

    assert not req.cookies


def test_flashes():
    req = Request()
    flashes = {"alert": "flash1", "notice": "flash2"}
    req._session = Dot({FLASHES_SESSION_KEY: flashes})

    assert req.flashes == req.flashes == flashes


@pytest.mark.parametrize(
    "method, result",
    [
        (GET, False),
        (POST, True),
        (PUT, True),
        (PATCH, True),
        (DELETE, True),
        (HEAD, False),
        (OPTIONS, False),
        ("MEH", False),
    ],
)
def test_must_check_csrf(method, result):
    assert Request(REQUEST_METHOD=method).must_check_csrf() == result
