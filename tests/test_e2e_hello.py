import pytest

from proper import App, View, get, status
from proper.concerns import RequestForgeryProtection, Session
from proper.current import response
from proper.errors import BadSecretKey


class Pages(View):
    concerns = [RequestForgeryProtection, Session]

    def index(self):
        response.mimetype = "text/plain"
        return "Hello World!"

    def charset(self):
        response.mimetype = "text/plain"
        response.charset = "latin-1"
        return "Hello World!"


def test_hello_world(app):
    app.routes = [get("/", to=Pages.index)]
    resp = app.get("/")

    assert resp.status == status.ok
    assert resp.body == "Hello World!"
    assert resp.mimetype == "text/plain"
    assert resp.content_type == "text/plain; charset=utf-8"


def test_charset(app):
    app.routes = [get("/charset", to=Pages.charset)]
    resp = app.get("/charset")
    assert resp.content_type == "text/plain; charset=latin-1"


def test_default_config(app):
    assert app.config.CATCH_ALL_ERRORS


def test_secret_key_too_short(import_name):
    with pytest.raises(BadSecretKey):
        App(import_name, config={"SECRET_KEYS": ["qwertyuiop"]})


def test_head(app):
    app.routes = [get("/", to=Pages.index)]
    resp = app.head("/")

    assert resp.status == status.ok
    assert resp.body == ""
