import pytest

from proper import App
from proper import MissingSecretKey
from proper import Request
from proper import Response
from proper.middleware import fetch_session


def test_error_if_no_secret_key(root_path):
    app = App(root_path)
    req = Request()
    resp = Response()

    with pytest.raises(MissingSecretKey):
        fetch_session(req, resp, app)


def test_no_session_to_fetch(app):
    req = Request()
    resp = Response()
    fetch_session(req, resp, app)

    assert req.session == resp.session == {}


def test_fetch_fetch_session(app):
    req = Request()
    resp = Response()
    serializer = app.get_serializer()
    data = {"hello": "world!"}
    req.cookies = {app.config.session.cookie_name: serializer.dumps(data)}
    fetch_session(req, resp, app)

    assert req.session == resp.session == data


def test_fetch_session_bad_cookie(app):
    req = Request()
    resp = Response()
    req.cookies = {app.config.session.cookie_name: "bad cookie"}
    fetch_session(req, resp, app)

    assert req.session == resp.session == {}
