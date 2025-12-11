import pytest

from proper import Request, Response, current
from proper.concerns import (
    CSRF_FORM_KEY,
    CSRF_HEADER,
    CSRF_SESSION_KEY,
    CSRF_TOKEN_LENGTH,
    RequestForgeryProtection,
)
from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.controller import Controller
from proper.errors import InvalidCSRFToken, MissingCSRFToken
from proper.helpers import MultiDict


class TestController(Controller, RequestForgeryProtection):
    skip_csrf_for = ["skipped"]

    def action(self):
        return "STOP"

    def skipped(self):
        return "SKIPPED"


@pytest.fixture
def co(app):
    request = Request()
    response = Response()
    return TestController(app, request, response)


def test_no_need_to_argue(co):
    co.request.method = GET
    co.request.matched_action = "action"
    co.before()

    csrf_token = current.csrf_token
    assert csrf_token is not None
    assert len(csrf_token) == CSRF_TOKEN_LENGTH * 2
    assert csrf_token == co.response.headers.get(CSRF_HEADER)
    assert csrf_token[CSRF_TOKEN_LENGTH:] == co.response.session[CSRF_SESSION_KEY]


def test_missing_csrf(co):
    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH}

    with pytest.raises(MissingCSRFToken):
        co.before()


def test_skip_csrf_check(co):
    co.request.method = POST
    co.request.matched_action = "skipped"
    co.request.session = {CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH}

    co.before()


def test_invalid_csrf_if_not_set(co):
    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {}

    with pytest.raises(InvalidCSRFToken):
        co.before()


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(co, method):
    co.request.method = method
    co.request.matched_action = "action"

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request._form = MultiDict({CSRF_FORM_KEY: mask + token})

    co.before()


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request._form = MultiDict({CSRF_FORM_KEY: mask + invalid_token})

    with pytest.raises(InvalidCSRFToken):
        co.before()


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.env[CSRF_HEADER] = mask + token

    co.before()


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.env[CSRF_HEADER] = mask + invalid_token

    with pytest.raises(InvalidCSRFToken):
        co.before()


def test_ignore_unmasked_tokens(co):
    token = "a" * CSRF_TOKEN_LENGTH

    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request._form = MultiDict({CSRF_FORM_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co.before()


def test_masking_is_random(co):
    co.request.method = GET
    co.request.matched_action = "action"

    co.before()
    token1 = current.csrf_token

    co.request.session = co.response.session.copy()
    co.before()
    token2 = current.csrf_token

    assert token1 != token2
    assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]
