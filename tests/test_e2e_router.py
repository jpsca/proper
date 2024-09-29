import pytest

from proper import Controller, status
from proper.errors import (
    BadRoutePlaceholder,
    MissingRouteParameter,
    RouteNotFound,
)
from proper.helpers import DotDict


class FooController(Controller):
    def bar(self):
        return "Hello World!"


class ItemsController(Controller):
    def index(self):
        return "index"

    def create(self):
        pass

    def show(self):
        return "show"

    def archive(self):
        return "archive"


def test_match_domain(app):
    app.router.debug = True
    app.router.get(host="example.com")(FooController.bar)

    resp = app.get("http://example.com/")
    assert resp.status == status.ok
    assert resp.body == "Hello World!"


def test_redirect(app):
    app.router.get(redirect="http://example.com")

    resp = app.get("/")
    assert resp.status == status.temporary_redirect
    assert resp.headers["location"] == "http://example.com"


def test_url_for(app):
    api = app.router.scope("api")
    api.get("items")(ItemsController.index)
    api.post("items")(ItemsController.create)
    api.get("items/:item_id")(ItemsController.show)
    api.get(r"items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    assert app.url_for("Items.index") == "/api/items"
    assert app.url_for("Items.create") == "/api/items"
    assert app.url_for("Items.show", item_id=3) == "/api/items/3"
    assert (
        app.url_for("Items.archive", year=2018, month=5) == "/api/items/2018/5"
    )


def test_url_for_object(app):
    api = app.router.scope("api")
    api.get(r"items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    object = DotDict({"year": 2018, "month": 5})
    assert app.url_for("Items.archive", object) == "/api/items/2018/5"


def test_url_for_anchor(app):
    app.router.get("login", name="login")(FooController.bar)
    url = app.url_for("login", _anchor="yeah")
    assert url == "/login#yeah"


def test_url_for_missing_param(app):
    app.router.get(r"items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    with pytest.raises(MissingRouteParameter):
        app.url_for("Items.archive", year="2018")


def test_url_for_bad_placeholder(app):
    app.router.get(r"items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    with pytest.raises(BadRoutePlaceholder):
        app.url_for("Items.archive", year=18, month=-3)


def test_url_for_extra_query(app):
    app.router.get(r"items")(ItemsController.index)
    app.router.get(r"items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    url = app.url_for("Items.index", foo="bar")
    assert url == "/items?foo=bar"

    url = app.url_for("Items.archive", year=2018, month=5, foo="bar")
    assert url == "/items/2018/5?foo=bar"


def test_url_for_not_found(app):
    app.router.get(r"items")(ItemsController.index)

    with pytest.raises(RouteNotFound):
        app.url_for("wtf")
