import pytest

from proper import Request, Response
from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.errors import InvalidCSRFToken, MissingCSRFToken
from proper.helpers import Dot
from proper.controller import (
    CSRF_HEADER,
    CSRF_FORM_KEY,
    CSRF_SESSION_KEY,
    CSRF_TOKEN_LENGTH,
    Controller,
)


def get_controller(method):
    req = Request(REQUEST_METHOD=method)
    resp = Response()
    req._session = resp._session = Dot()
    return Controller(req=req, resp=resp)


def test_no_need_to_argue():
    co = get_controller(GET)
    co.protect_from_forgery("action")
    assert co.req.csrf_token is not None
    assert co.req.csrf_token == co.resp.headers[CSRF_HEADER]
    assert len(co.req.csrf_token) == CSRF_TOKEN_LENGTH * 2


def test_missing_csrf():
    co = get_controller(POST)
    token = "a" * CSRF_TOKEN_LENGTH
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co.protect_from_forgery("action")


def test_invalid_csrf_if_not_set():
    co = get_controller(POST)

    with pytest.raises(InvalidCSRFToken):
        co.protect_from_forgery("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.req._form = Dot({CSRF_FORM_KEY: mask + token})
    co.req._content_length = 1  # needs to be truthy for this test
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    co.protect_from_forgery("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.req._form = Dot({CSRF_FORM_KEY: mask + invalid_token})
    co.req._content_length = 1  # needs to be truthy for this test
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    with pytest.raises(InvalidCSRFToken):
        co.protect_from_forgery("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.req.env[CSRF_HEADER] = mask + token
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    co.protect_from_forgery("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.req.env[CSRF_HEADER] = mask + invalid_token
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    with pytest.raises(InvalidCSRFToken):
        co.protect_from_forgery("action")


def test_unmasked_csrf_is_ignored():
    co = get_controller(POST)
    token = "a" * CSRF_TOKEN_LENGTH

    co.req._form = Dot({CSRF_FORM_KEY: token})
    co.req._content_length = 1  # needs to be truthy for this test
    co.req._session = Dot({CSRF_SESSION_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co.protect_from_forgery("action")


def test_skip_csrf_check():
    co = get_controller(POST)
    co.skip_csrf_check_for = ["action"]
    co.protect_from_forgery("action")

    co.req._session = Dot({CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH})
    co.protect_from_forgery("action")


def test_random_masking():
    co = get_controller(GET)
    co.protect_from_forgery("action")
    token1 = co.req.csrf_token
    co.protect_from_forgery("action")
    token2 = co.req.csrf_token

    assert token1 != token2
    assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]
