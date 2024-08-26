from http.cookies import Morsel

import pytest

from proper import Request, Response
from proper.concerns import SESSION_SALT, Session
from proper.constants import FLASHES_SESSION_KEY
from proper.view import View


@pytest.fixture
def view(app):
    request = Request()
    response = Response()
    return View(app, request, response)


def _set_request_cookie(app, view, value):
    cookie_name = app.config.SESSION_COOKIE_NAME
    cookie = Morsel()
    cookie.set(cookie_name, value, 0)
    view.request.cookie = {cookie_name: cookie}


def test_fetch_session(app, view):
    mid = Session()
    data = {"hello": "world!"}
    _set_request_cookie(app, view, app.serializer.dumps(data, salt=SESSION_SALT))
    mid.before(view)

    assert view.request.session == view.response.session == data


def test_do_not_copy_flashes(app, view):
    mid = Session()
    data = {"hello": "world!"}
    ext_data = {FLASHES_SESSION_KEY: "...", **data}
    _set_request_cookie(app, view, app.serializer.dumps(ext_data, salt=SESSION_SALT))
    mid.before(view)

    assert view.request.session == ext_data
    assert view.response.session == data


def test_fetch_session_bad_cookie(app, view):
    mid = Session()
    _set_request_cookie(app, view, "bad cookie")
    mid.before(view)

    assert view.request.session == view.response.session == {}


def test_do_not_set_cookie_if_not_data(app, view):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    view.request.session = {}
    view.response.session = {}
    mid.after(view)

    assert cookie_name not in view.response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app, view):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    view.request.session = {"foo": "bar"}
    view.response.session = {}
    mid.after(view)

    assert cookie_name in view.response.cookies
    assert view.response.cookies[cookie_name].value == ""
    assert view.response.cookies[cookie_name]["max-age"] == 0
