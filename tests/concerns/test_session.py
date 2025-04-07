from http.cookies import Morsel

import pytest

from proper import Request, Response
from proper.concerns import SESSION_SALT, RestoreSession, UpdateSessionCookie
from proper.constants import FLASHES_SESSION_KEY
from proper.controller import Controller


@pytest.fixture
def co(app):
    request = Request()
    response = Response()
    return Controller(app, request, response)


def _set_request_cookie(app, co, value):
    cookie_name = app.config.SESSION_COOKIE_NAME
    cookie = Morsel()
    cookie.set(cookie_name, value, 0)
    co.request.cookie = {cookie_name: cookie}


def test_fetch_session(app, co):
    concern = RestoreSession()
    data = {"hello": "world!"}
    _set_request_cookie(app, co, app.serializer.dumps(data, salt=SESSION_SALT))
    concern(co)

    assert co.request.session == co.response.session == data


def test_do_not_copy_flashes(app, co):
    concern = RestoreSession()
    data = {"hello": "world!"}
    ext_data = {FLASHES_SESSION_KEY: "...", **data}
    _set_request_cookie(app, co, app.serializer.dumps(ext_data, salt=SESSION_SALT))
    concern(co)

    assert co.request.session == ext_data
    assert co.response.session == data


def test_fetch_session_bad_cookie(app, co):
    concern = RestoreSession()
    _set_request_cookie(app, co, "bad cookie")
    concern(co)

    assert co.request.session == co.response.session == {}


def test_do_not_set_cookie_if_not_data(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    concern = UpdateSessionCookie()
    co.request.session = {}
    co.response.session = {}
    concern(co)

    assert cookie_name not in co.response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    concern = UpdateSessionCookie()
    co.request.session = {"foo": "bar"}
    co.response.session = {}
    concern(co)

    assert cookie_name in co.response.cookies
    assert co.response.cookies[cookie_name].value == ""
    assert co.response.cookies[cookie_name]["max-age"] == 0
