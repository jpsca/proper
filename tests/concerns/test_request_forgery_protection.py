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
from proper.helpers.asgi import make_test_scope


class _TestController(RequestForgeryProtection, Controller):
    def action(self):
        return "STOP"


def _make_co(app, **scope_kw):
    scope = make_test_scope(**scope_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return _TestController(request, response)


@pytest.fixture
def co(app):
    return _make_co(app)


def test_no_need_to_argue(co):
    co.request.method = GET
    co.request.matched_action = "action"
    co._dispatch("action")

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
        co._dispatch("action")


def test_invalid_csrf_if_not_set(co):
    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {}

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(co, method):
    co.request.method = method
    co.request.matched_action = "action"

    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.form = MultiDict({CSRF_FORM_KEY: mask + token})

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.form = MultiDict({CSRF_FORM_KEY: mask + invalid_token})

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.headers["x-csrf-token"] = mask + token

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(co, method):
    mask = "x" * CSRF_TOKEN_LENGTH
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.headers["x-csrf-token"] = mask + invalid_token

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


def test_ignore_unmasked_tokens(co):
    token = "a" * CSRF_TOKEN_LENGTH

    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.form = MultiDict({CSRF_FORM_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co._dispatch("action")


def test_masking_is_random(co):
    co.request.method = GET
    co.request.matched_action = "action"

    co._dispatch("action")
    token1 = current.csrf_token

    co.request.session = co.response.session.copy()
    co._dispatch("action")
    token2 = current.csrf_token

    assert token1 != token2
    assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]
