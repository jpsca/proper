import pytest

import proper
from proper.controller import Controller, Session
from proper.helpers import DotDict


class AppController(Controller, Session):
    pass


@pytest.fixture
def req():
    return proper.Request()


@pytest.fixture
def resp():
    return proper.Response()


@pytest.fixture
def tc(app, req, resp):
    req._session = resp._session = DotDict()
    return AppController(app=app, request=req, response=resp)


def serialize_cookie(app, value):
    return app.serializer.dumps({"foo": "bar"})


def test_no_session_to_fetch(app, tc):
    tc._fetch_session()
    assert tc.request.session == tc.response.session == {}


def test_fetch_fetch_session(app, tc):
    data = {"hello": "world!"}
    tc.request.cookie = {"_session": app.serializer.dumps(data)}
    tc._fetch_session()

    assert tc.request.session == tc.response.session == data


def test_fetch_session_bad_cookie(app, tc):
    tc.request.cookie = {"_session": "bad cookie"}  # type: ignore
    tc._fetch_session()

    assert tc.request.session == tc.response.session == {}


def test_set_cookie(app, tc):
    tc._fetch_session()
    tc.response.dispatched = True
    tc.response.session["foo"] = "bar"
    tc._put_session()

    expected = serialize_cookie(app, {"foo": "bar"})
    cookie = tc.response.cookies["_session"]
    assert cookie.value == expected


def test_do_not_set_cookie_if_not_data(app, tc):
    tc._fetch_session()
    tc.response.dispatched = True
    tc.response._session = DotDict()
    tc._put_session()

    assert "_session" not in tc.response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app, tc):
    expected = serialize_cookie(app, {"foo": "bar"})
    tc.request.cookies["_session"] = expected
    tc._fetch_session()

    tc.response.dispatched = True
    del tc.response.session["foo"]
    tc._put_session()

    cookie_name = "_session"
    assert cookie_name in tc.response.cookies
    assert tc.response.cookies[cookie_name].value == ""
    assert tc.response.cookies[cookie_name]["max-age"] == 0
