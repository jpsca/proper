from proper import Request
from proper import Response
from proper.helpers import DotDict
from proper.middleware import fetch_session, put_session


def serialize_cookie(app, value):
    return app.serializer.dumps({"foo": "bar"})


def test_set_cookie(app):
    request = Request()
    response = Response()

    fetch_session(request, response, app)
    response.dispatched = True
    response.session["foo"] = "bar"
    put_session(request, response, app)

    expected = serialize_cookie(app, {"foo": "bar"})
    print(response.cookies)
    assert response.cookies[app.config.session.cookie.name].value == expected


def test_do_not_set_cookie_if_not_data(app):
    request = Request()
    response = Response()

    fetch_session(request, response, app)
    response.dispatched = True
    response._session = DotDict()
    put_session(request, response, app)

    assert app.config.session.cookie.name not in response.cookies


def test_set_delete_cookie_if_not_data_and_modified(app):
    request = Request()
    response = Response()

    expected = serialize_cookie(app, {"foo": "bar"})
    request.cookies[app.config.session.cookie.name] = expected
    fetch_session(request, response, app)

    response.dispatched = True
    del response.session["foo"]
    put_session(request, response, app)

    cookie_name = app.config.session.cookie.name
    assert cookie_name in response.cookies
    assert response.cookies[cookie_name].value == ""
    assert response.cookies[cookie_name]["max-age"] == 0
