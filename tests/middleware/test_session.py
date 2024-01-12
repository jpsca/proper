import pytest

from proper import Request, Response, current
from proper.constants import FLASHES_SESSION_KEY
from proper.view import View
from proper.middleware import Session


@pytest.fixture
def co(app):
    request = Request()
    current.request._set(request)
    response = Response()
    current.response._set(response)
    return View(app, request, response)


def test_fetch_fetch_session(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    data = {"hello": "world!"}
    co.request.cookie = {cookie_name: app.serializer.dumps(data)}
    mid.before(co)

    assert co.request.session == co.response.session == data


def test_do_not_copy_flashes(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    data = {"hello": "world!"}
    extdata = {FLASHES_SESSION_KEY: "...", **data}
    co.request.cookie = {cookie_name: app.serializer.dumps(extdata)}
    mid.before(co)

    assert co.request.session == extdata
    assert co.response.session == data


def test_fetch_session_bad_cookie(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    co.request.cookie = {cookie_name: "bad cookie"}  # type: ignore
    mid.before(co)

    assert co.request.session == co.response.session == {}


def test_set_cookie(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    co.request.session = {}
    co.response.session = {"foo": "bar"}
    mid.after(co)

    expected = app.serializer.dumps({"foo": "bar"})
    cookie = co.response.cookies[cookie_name]
    assert cookie.value == expected


def test_do_not_set_cookie_if_not_data(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    co.request.session = {}
    co.response.session = {}
    mid.after(co)

    assert cookie_name not in co.response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app, co):
    cookie_name = app.config.SESSION_COOKIE_NAME
    mid = Session()
    co.request.session = {"foo": "bar"}
    co.response.session = {}
    mid.after(co)

    assert cookie_name in co.response.cookies
    assert co.response.cookies[cookie_name].value == ""
    assert co.response.cookies[cookie_name]["max-age"] == 0
