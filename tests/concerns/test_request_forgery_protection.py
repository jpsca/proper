import pytest

from proper import Response, current
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
from proper.test_client import make_test_request


class _TestController(RequestForgeryProtection, Controller):
    def action(self):
        return "STOP"


def _make_co(app, **scope_kw):
    request = make_test_request(app=app, **scope_kw)
    response = Response(app)
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
    assert csrf_token == co.response.headers.get(CSRF_HEADER)
    session_token = co.response.session[CSRF_SESSION_KEY]
    assert len(session_token) == CSRF_TOKEN_LENGTH
    assert co._unmask_csrf_token(csrf_token) == session_token.encode()


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

    token = "a" * CSRF_TOKEN_LENGTH
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.form = MultiDict({CSRF_FORM_KEY: co._mask_csrf_token(token)})

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(co, method):
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.form = MultiDict({CSRF_FORM_KEY: co._mask_csrf_token(invalid_token)})

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(co, method):
    token = "a" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.headers["x-csrf-token"] = co._mask_csrf_token(token)

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(co, method):
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH

    co.request.method = method
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: token}
    co.request.headers["x-csrf-token"] = co._mask_csrf_token(invalid_token)

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
    assert co._unmask_csrf_token(token1) == co._unmask_csrf_token(token2)


def test_masked_token_hides_the_token(co):
    token = "a" * CSRF_TOKEN_LENGTH
    masked = [co._mask_csrf_token(token) for _ in range(2)]

    for value in masked:
        assert token not in value
    # no part of the token repeats from one response to the next
    assert masked[0][len(masked[0]) // 2:] != masked[1][len(masked[1]) // 2:]


@pytest.mark.parametrize("value", [
    "!" * 88,  # not base64: it decodes to nothing
    "ñ" * 88,  # not ASCII
    "A" * 88,  # base64, but not of the session's token
])
def test_malformed_masked_token(co, value):
    co.request.method = POST
    co.request.matched_action = "action"
    co.request.session = {CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH}
    co.request.form = MultiDict({CSRF_FORM_KEY: value})

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")
