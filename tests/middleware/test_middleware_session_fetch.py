from proper import Request, Response
from proper.middleware import fetch_session


def test_no_session_to_fetch(app):
    request = Request()
    response = Response()
    fetch_session(request, response, app)

    assert request.session == response.session == {}


def test_fetch_fetch_session(app):
    request = Request()
    response = Response()
    data = {"hello": "world!"}
    request._cookies = {app.config.session.cookie.name: app.serializer.dumps(data)}
    fetch_session(request, response, app)

    assert request.session == response.session == data


def test_fetch_session_bad_cookie(app):
    request = Request()
    response = Response()
    request._cookies = {app.config.session.cookie.name: "bad cookie"}
    fetch_session(request, response, app)

    assert request.session == response.session == {}
