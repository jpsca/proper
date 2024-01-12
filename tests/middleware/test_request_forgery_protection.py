import pytest

from proper import Request, Response, current
from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.view import View
from proper.middleware import (
    CSRF_HEADER,
    CSRF_FORM_KEY,
    CSRF_SESSION_KEY,
    CSRF_TOKEN_LENGTH,
    RequestForgeryProtection
)
from proper.errors import InvalidCSRFToken, MissingCSRFToken
from proper.helpers import MultiDict


class AppView(View):
    def action(self):
        return "STOP"

    def skipped(self):
        return "SKIPPED"


@pytest.fixture
def co(app):
    request = Request()
    current.request._set(request)
    response = Response()
    current.response._set(response)
    return AppView(app, request, response)


def test_no_need_to_argue(co):
    mid = RequestForgeryProtection(skip_for=["skipped"])
    request = co.request
    response = co.response

    request.method = GET
    request.matched_action = "action"
    mid.before(co)

    assert request.csrf_token is not None
    assert len(request.csrf_token) == CSRF_TOKEN_LENGTH * 2
    assert request.csrf_token == response.headers[CSRF_HEADER]
    assert request.csrf_token[CSRF_TOKEN_LENGTH:] == response.session[CSRF_SESSION_KEY]


def test_missing_csrf(co):
    mid = RequestForgeryProtection(skip_for=["skipped"])
    request = co.request

    request.method = POST
    request.matched_action = "action"
    token = "a" * CSRF_TOKEN_LENGTH
    request.session = {CSRF_SESSION_KEY: token}

    with pytest.raises(MissingCSRFToken):
        mid.before(co)


def test_skip_csrf_check(co):
    mid = RequestForgeryProtection(skip_for=["skipped"])
    request = co.request

    token = "a" * CSRF_TOKEN_LENGTH
    request.method = POST
    request.matched_action = "skipped"
    request.session = {CSRF_SESSION_KEY: token}

    mid.before(co)


def test_invalid_csrf_if_not_set(co):
    mid = RequestForgeryProtection()
    request = co.request

    request.method = POST
    request.matched_action = "action"
    request.session = {}

    with pytest.raises(InvalidCSRFToken):
        mid.before(co)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(co, method):
    mid = RequestForgeryProtection()
    request = co.request

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH

    request.method = method
    request.matched_action = "action"
    request.session = {CSRF_SESSION_KEY: token}
    request._form = MultiDict({CSRF_FORM_KEY: mask + token})

    mid.before(co)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(co, method):
    mid = RequestForgeryProtection()
    request = co.request

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    request.method = method
    request.matched_action = "action"
    request.session = {CSRF_SESSION_KEY: token}
    request._form = MultiDict({CSRF_FORM_KEY: mask + invalid_token})

    with pytest.raises(InvalidCSRFToken):
        mid.before(co)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(co, method):
    mid = RequestForgeryProtection()
    request = co.request

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH

    request.method = method
    request.matched_action = "action"
    request.session = {CSRF_SESSION_KEY: token}
    request.env[CSRF_HEADER] = mask + token

    mid.before(co)


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(co, method):
    mid = RequestForgeryProtection()
    request = co.request

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    request.method = method
    request.matched_action = "action"
    request.session = {CSRF_SESSION_KEY: token}
    request.env[CSRF_HEADER] = mask + invalid_token

    with pytest.raises(InvalidCSRFToken):
        mid.before(co)


def test_ignore_unmasked_tokens(co):
    mid = RequestForgeryProtection()
    request = co.request

    token = "a" * CSRF_TOKEN_LENGTH

    request.method = POST
    request.matched_action = "action"
    request.session = {CSRF_SESSION_KEY: token}
    request._form = MultiDict({CSRF_FORM_KEY: token})

    with pytest.raises(MissingCSRFToken):
        mid.before(co)


def test_masking_is_random(co):
    mid = RequestForgeryProtection(skip_for=["skipped"])
    request = co.request
    response = co.response

    request.method = GET
    request.matched_action = "action"

    mid.before(co)
    token1 = request.csrf_token

    request.session = response.session.copy()
    mid.before(co)
    token2 = request.csrf_token

    assert token1 != token2
    assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]
