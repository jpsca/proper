import pytest

from proper import Request, Response, current
from proper.controller import Controller
from proper.middleware import Session
from proper.helpers import DotDict


class AppController(Controller):
    middleware = [Session]


@pytest.fixture
def co(app):
    request = Request()
    current.request._set(request)
    response = Response()
    current.response._set(response)
    return AppController(request, response)


def serialize_cookie(app, value):
    return app.serializer.dumps({"foo": "bar"})


def test_fetch_fetch_session(app, co):
    data = {"hello": "world!"}
    co.request.cookie = {"_session": app.serializer.dumps(data)}
    co._fetch_session()

    assert co.request.session == co.response.session == data


def test_fetch_session_bad_cookie(app, co):
    co.request.cookie = {"_session": "bad cookie"}  # type: ignore
    co._fetch_session()

    assert co.request.session == co.response.session == {}


def test_set_cookie(app, co):
    co._fetch_session()
    co.response.dispatched = True
    co.response.session["foo"] = "bar"
    co._put_session()

    expected = serialize_cookie(app, {"foo": "bar"})
    cookie = co.response.cookies["_session"]
    assert cookie.value == expected


def test_do_not_set_cookie_if_not_data(app, co):
    co._fetch_session()
    co.response.dispatched = True
    co.response.session = DotDict()
    co._put_session()

    assert "_session" not in co.response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app, co):
    expected = serialize_cookie(app, {"foo": "bar"})
    co.request.cookies["_session"] = expected
    co._fetch_session()

    co.response.dispatched = True
    del co.response.session["foo"]
    co._put_session()

    cookie_name = "_session"
    assert cookie_name in co.response.cookies
    assert co.response.cookies[cookie_name].value == ""
    assert co.response.cookies[cookie_name]["max-age"] == 0
