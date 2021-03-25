import pytest

from proper import Request, Response
from proper.constants import DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT
from proper.errors import InvalidCSRFToken, MissingCSRFToken
from proper.helpers import Dot
from proper.middleware.protect_from_forgery import (
    CSRF_HEADER,
    CSRF_HEADER_ALT,
    CSRF_QUERY_KEY,
    CSRF_SESSION_KEY,
    get_or_set_token,
    protect_from_forgery,
)


@pytest.mark.parametrize("method", [GET, HEAD, OPTIONS, "MEH"])
def test_no_need_to_argue(method):
    req = Request(REQUEST_METHOD=method)
    req._session = Dot()
    resp = Response()
    protect_from_forgery(req, resp, None)

    assert req.csrf_token is not None


def test_missing_csrf():
    req = Request(REQUEST_METHOD=POST)
    resp = Response()

    with pytest.raises(MissingCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(method):
    req = Request(REQUEST_METHOD=method)
    req._form = Dot({CSRF_QUERY_KEY: "qwertyuiop"})
    req._content_length = 10
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(method):
    req = Request(REQUEST_METHOD=method)
    req._form = Dot({CSRF_QUERY_KEY: "hello"})
    req._content_length = 10
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_query(method):
    req = Request(REQUEST_METHOD=method, QUERY_STRING=f"{CSRF_QUERY_KEY}=qwertyuiop")
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_query(method):
    req = Request(REQUEST_METHOD=method, QUERY_STRING=f"{CSRF_QUERY_KEY}=hello")
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(method):
    req = Request(REQUEST_METHOD=method)
    req.environ[CSRF_HEADER] = "qwertyuiop"
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(method):
    req = Request(REQUEST_METHOD=method)
    req.environ[CSRF_HEADER] = "hello"
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_alt_header(method):
    req = Request(REQUEST_METHOD=method)
    req.environ[CSRF_HEADER_ALT] = "qwertyuiop"
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    protect_from_forgery(req, resp, None)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_alt_header(method):
    req = Request(REQUEST_METHOD=method)
    req.environ[CSRF_HEADER_ALT] = "hello"
    req._session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    resp = Response()

    with pytest.raises(InvalidCSRFToken):
        protect_from_forgery(req, resp, None)


def test_get_existing_token_from_session():
    req = Request()
    resp = Response()
    session = Dot({CSRF_SESSION_KEY: "qwertyuiop"})
    req._session = session
    req._session = session

    assert get_or_set_token(req, resp) == "qwertyuiop"


def test_get_new_token_from_session():
    req = Request()
    resp = Response()
    session = Dot()
    req._session = session
    req._session = session

    assert get_or_set_token(req, resp) is not None
