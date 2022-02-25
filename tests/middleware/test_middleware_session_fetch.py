from proper import Request, Response
from proper.middleware import fetch_session


def test_no_session_to_fetch(app):
    req = Request()
    resp = Response()
    fetch_session(req, resp, app)

    assert req.session == resp.session == {}


def test_fetch_fetch_session(app):
    req = Request()
    resp = Response()
    data = {"hello": "world!"}
    req._cookies = {app.config.session.cookie.name: app.serializer.dumps(data)}
    fetch_session(req, resp, app)

    assert req.session == resp.session == data


def test_fetch_session_bad_cookie(app):
    req = Request()
    resp = Response()
    req._cookies = {app.config.session.cookie.name: "bad cookie"}
    fetch_session(req, resp, app)

    assert req.session == resp.session == {}
