import pytest

from proper import Request, Response
from proper.constants import GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
from proper.errors import InvalidCSRFToken
from proper.errors import MissingCSRFToken
from proper.support import Dot
from proper.plugs.protect_from_forgery import (
    CSRF_HEADER,
    CSRF_HEADER_ALT,
    CSRF_QUERY_KEY,
    CSRF_SESSION_KEY,
    get_or_set_token,
    protect_from_forgery,
)


@pytest.mark.parametrize("method", [GET, HEAD, OPTIONS, "MEH"])
def test_no_need_to_argue(method):
    req = Request(method=method)
    req._Request__session = Dot()
    resp = Response()
    protect_from_forgery(req, resp, None)

    assert req.csrf_token is not None


def test_missing_csrf():
    req = Request(method=POST)
    resp = Response()

    with pytest.raises(MissingCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(method):
    req = Request(method=method, path="/")
    req.form = Dot({CSRF_QUERY_KEY: "qwertyuiop"})
    req.content_length = 10
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(method):
    req = Request(method=method, path="/")
    req.form = Dot({CSRF_QUERY_KEY: "hello"})
    req.content_length = 10
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_query(method):
    req = Request(method=method, path=f"/?{CSRF_QUERY_KEY}=qwertyuiop")
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_query(method):
    req = Request(method=method, path=f"/?{CSRF_QUERY_KEY}=hello")
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(method):
    req = Request(method=method, path="/")
    req.environ[CSRF_HEADER] = "qwertyuiop"
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(method):
    req = Request(method=method, path="/")
    req.environ[CSRF_HEADER] = "hello"
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_alt_header(method):
    req = Request(method=method, path="/")
    req.environ[CSRF_HEADER_ALT] = "qwertyuiop"
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_alt_header(method):
    req = Request(method=method, path="/")
    req.environ[CSRF_HEADER_ALT] = "hello"
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


def test_get_existing_token_from_session():
    req = Request()
    req._Request__session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})

    assert get_or_set_token(req) == "qwertyuiop"


def test_get_new_token_from_session():
    req = Request()
    req._Request__session = Dot()
    print(get_or_set_token(req))

    assert get_or_set_token(req) is not None
