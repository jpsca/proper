import pytest

from proper import Request, Response, current
from proper.constants import DELETE, GET, PATCH, POST, PUT
from proper.controller import Controller
from proper.middleware import (
    CSRF_HEADER,
    CSRF_FORM_KEY,
    CSRF_SESSION_KEY,
    CSRF_TOKEN_LENGTH,
    RequestForgeryProtection
)
from proper.errors import InvalidCSRFToken, MissingCSRFToken
from proper.helpers import DotDict, MultiDict


HTTP_CSRF_HEADER = f"HTTP_{CSRF_HEADER}"


class AppController(Controller):
    middleware = [
        RequestForgeryProtection(skip_for=["skipped"])
    ]

    def action(self):
        return "STOP"

    def skipped(self):
        return "SKIPPED"


def get_controller(method, **env):
    env["REQUEST_METHOD"] = method
    request = Request()
    current.request._set(request)
    response = Response()
    current.response._set(response)
    return AppController(request, response)


def test_no_need_to_argue():
    co = get_controller(GET)
    co._dispatch("action")
    assert co.request.csrf_token is not None
    assert co.request.csrf_token == co.response.headers[CSRF_HEADER]
    assert len(co.request.csrf_token) == CSRF_TOKEN_LENGTH * 2


def test_missing_csrf():
    co = get_controller(POST)
    token = "a" * CSRF_TOKEN_LENGTH
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co._dispatch("action")


def test_invalid_csrf_if_not_set():
    co = get_controller(POST)

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_form(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.request._form = MultiDict({CSRF_FORM_KEY: mask + token})
    co.request.content_length = 1  # needs to be truthy for this test
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_form(method):
    co = get_controller(method)
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    co.request._form = MultiDict({CSRF_FORM_KEY: mask + invalid_token})
    co.request.content_length = 1  # needs to be truthy for this test
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_valid_csrf_from_header(method):
    token = "a" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    env = {HTTP_CSRF_HEADER: mask + token}
    co = get_controller(method, **env)
    print(co.request.env)
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    co._dispatch("action")


@pytest.mark.parametrize("method", [POST, PUT, PATCH, DELETE])
def test_invalid_csrf_from_header(method):
    token = "a" * CSRF_TOKEN_LENGTH
    invalid_token = "b" * CSRF_TOKEN_LENGTH
    mask = "x" * CSRF_TOKEN_LENGTH

    env = {HTTP_CSRF_HEADER: mask + invalid_token}
    co = get_controller(method, **env)
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    with pytest.raises(InvalidCSRFToken):
        co._dispatch("action")


def test_unmasked_csrf_is_ignored():
    co = get_controller(POST)
    token = "a" * CSRF_TOKEN_LENGTH

    co.request._form = MultiDict({CSRF_FORM_KEY: token})
    co.request.content_length = 1  # needs to be truthy for this test
    co.request.session = DotDict({CSRF_SESSION_KEY: token})

    with pytest.raises(MissingCSRFToken):
        co._dispatch("action")


def test_skip_csrf_check():
    co = get_controller(POST)
    co._dispatch("skipped")

    co.request.session = DotDict({CSRF_SESSION_KEY: "a" * CSRF_TOKEN_LENGTH})
    co._dispatch("skipped")


def test_random_masking():
    co = get_controller(GET)
    co._dispatch("action")
    token1 = co.request.csrf_token
    co._dispatch("action")
    token2 = co.request.csrf_token

    assert token1 != token2
    assert token1[CSRF_TOKEN_LENGTH:] == token2[CSRF_TOKEN_LENGTH:]
