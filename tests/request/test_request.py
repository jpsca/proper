import pytest

from proper.constants import FLASHES_SESSION_KEY
from proper.errors import InvalidHeader
from proper.helpers import DotDict
from proper.request import Request


def test_query():
    request = Request(QUERY_STRING="foo=bar&ok&color=red&color=green&color=blue")

    assert request.query
    assert request.query == request.query  # idempotent
    assert request.query.get("foo") == "bar"
    assert request.query.get("ok") == ""
    assert request.query.getall("color") == ["red", "green", "blue"]


def test_empty_body():
    request = Request()

    assert request.form is not None
    assert not request.form
    assert request.form == request.form  # idempotent


def test_no_content_length():
    request = Request()
    assert request.content_length == 0


def test_content_length():
    request = Request(CONTENT_LENGTH="456789")
    assert request.content_length == 456_789
    assert request.content_length == request.content_length


def test_invalid_content_length():
    with pytest.raises(InvalidHeader):
        Request(CONTENT_LENGTH="very large")


def test_negative_content_length():
    with pytest.raises(InvalidHeader):
        Request(CONTENT_LENGTH="-456789")


def test_extra_content_length():
    with pytest.raises(InvalidHeader):
        Request(CONTENT_LENGTH="3434 or something")


def test_parse_host():
    request = Request(HTTP_HOST="0.0.0.0")
    assert request.host == "0.0.0.0"
    assert request.port == 80

    request = Request(HTTP_HOST="0.0.0.0:5000")
    assert request.host == "0.0.0.0"
    assert request.port == 5000

    request = Request(HTTP_HOST="localhost")
    assert request.host == "localhost"
    assert request.port == 80

    ipv6_addr = "2800:200:e480:10d4:dc9e:51f0:f99e:b5f4"
    request = Request(HTTP_HOST="[" + ipv6_addr + "]")
    assert request.host == ipv6_addr
    assert request.port == 80

    request = Request(HTTP_HOST="[" + ipv6_addr + "]:34567")
    assert request.host == ipv6_addr
    assert request.port == 34567

    request = Request(HTTP_HOST="example.com")
    assert request.host == "example.com"
    assert request.port == 80

    request = Request(HTTP_HOST="proper.jpscaletti.com")
    assert request.host == "proper.jpscaletti.com"
    assert request.port == 80

    request = Request(HTTP_HOST="proper.jpscaletti.com:4000")
    assert request.host == "proper.jpscaletti.com"
    assert request.port == 4000

    request = Request(HTTP_HOST="example.com", HTTP_X_FORWARDED_PROTO="https")
    assert request.host == "example.com"
    assert request.port == 443


def test_host_with_port():
    request = Request(HTTP_HOST="example.com")
    assert request.host_with_port == "example.com"

    request = Request(HTTP_HOST="example.com:80")
    assert request.host_with_port == "example.com"

    request = Request(HTTP_HOST="example.com:5000")
    assert request.host_with_port == "example.com:5000"

    request = Request(HTTP_HOST="example.com:443")
    assert request.host_with_port == "example.com:443"

    request = Request(HTTP_HOST="example.com:443", HTTP_X_FORWARDED_PROTO="https")
    assert request.host_with_port == "example.com"


def test_remote_addr():
    request = Request(REMOTE_ADDR="192.168.56.1")
    assert request.remote_ip == "192.168.56.1"


def test_x_remote_addr():
    request = Request(HTTP_X_REAL_IP="172.217.15.206", REMOTE_ADDR="localhost")
    assert request.remote_ip == "172.217.15.206"


def test_no_cookies():
    request = Request()

    assert request.cookies == request.cookies
    assert not request.cookies


def test_cookies():
    header = "logged_in=yes; _octo=GH1.1.19797273.434; has_recent_activity=1;"
    request = Request(HTTP_COOKIE=header)

    assert request.cookies == request.cookies
    assert request.cookies["logged_in"].value == "yes"
    assert request.cookies["_octo"].value == "GH1.1.19797273.434"
    assert request.cookies["has_recent_activity"].value == "1"


def test_parse_one_value():
    header = "dismiss=6"
    request = Request(HTTP_COOKIE=header)

    assert request.cookies["dismiss"].value == "6"


def test_parse_invalid_cookies():
    header = "this is not a cookie"
    request = Request(HTTP_COOKIE=header)

    assert not request.cookies


def test_flashes():
    request = Request()
    flashes = {"alert": "flash1", "notice": "flash2"}
    request.session = DotDict({FLASHES_SESSION_KEY: flashes})

    assert request.flashes == request.flashes == flashes
