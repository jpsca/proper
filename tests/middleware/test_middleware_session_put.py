from proper import Request
from proper import Response
from proper.helpers import Dot
from proper.middleware import fetch_session, put_session


def serialize_cookie(app, value):
    return app.serializer.dumps({"foo": "bar"})


def test_set_cookie(app):
    req = Request()
    resp = Response()
    fetch_session(req, resp, app)
    resp.dispatched = True
    resp.session["foo"] = "bar"
    put_session(req, resp, app)

    expected = serialize_cookie(app, {"foo": "bar"})
    print(resp.cookies)
    assert resp.cookies[app.config.session.cookie.name].value == expected


def test_do_not_set_cookie_if_not_data(app):
    req = Request()
    resp = Response()
    fetch_session(req, resp, app)
    resp.dispatched = True
    resp._session = Dot()
    put_session(req, resp, app)

    assert app.config.session.cookie.name not in resp.cookies


def test_set_delete_cookie_if_not_data_and_modified(app):
    req = Request()
    resp = Response()

    expected = serialize_cookie(app, {"foo": "bar"})
    req.cookies[app.config.session.cookie.name] = expected
    fetch_session(req, resp, app)

    resp.dispatched = True
    del resp.session["foo"]
    put_session(req, resp, app)

    cookie_name = app.config.session.cookie.name
    assert cookie_name in resp.cookies
    assert resp.cookies[cookie_name].value == ""
    assert resp.cookies[cookie_name]["max-age"] == 0
