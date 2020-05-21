import pytest

from proper.constants import GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
from proper.errors import InvalidHeader
from proper.request import FLASHES_SESSION_KEY
from proper.request import make_test_environ
from proper.request import Request
from proper.support import Dot


def test_query():
    req = Request(method=GET, path="/?foo=bar&ok&color=red&color=green&color=blue")

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
    env = make_test_environ(method=GET, host="example.com")
    req = Request(env)

    assert req.host == "example.com"


def test_parse_port_in_host():
    env = make_test_environ(method=GET, host="example.com:4567")
    req = Request(env)

    assert req.host == "example.com"


def test_no_remote_addr():
    req = Request()
    if "REMOTE_ADDR" in req.environ:
        del req.environ["REMOTE_ADDR"]
    assert req.remote_addr is None


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
    flashes = [("flash1", {}), ("flash2", {})]
    req._Request__session = Dot({FLASHES_SESSION_KEY: flashes})

    assert req.flashes == req.flashes
    assert req.flashes == flashes
    assert not req.session.get(FLASHES_SESSION_KEY)


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
    assert Request(method=method).must_check_csrf() == result
