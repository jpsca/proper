import pytest

from proper import (
    BadPlaceholder,
    BaseController,
    MissingParameter,
    NameNotFound,
    delete,
    get,
    post,
    scope,
    status,
)
from proper.helpers import Dot


class Foo(BaseController):
    def bar(self):
        self.resp.body = "Hello World!"


class Items(BaseController):
    def index(self):
        self.resp.body = "index"

    def create(self):
        pass

    def show(self):
        self.resp.body = "show"

    def archive(self):
        self.resp.body = "archive"

    def delete(self):
        pass


TEST_ROUTES = [
    scope("/api/")(
        get("items", to=Items.index),
        post("/items", to=Items.create),
        get("items/:item_id<int>", to=Items.show),
        get(r"items/:year<\d{4}>/:month<\d{1,2}>", to=Items.archive),
        delete("/items/:item_id<int>", to=Items.delete),
    ),

    scope("/foobar/")(
        get(""),
        get("foo"),
        get("bar"),
    ),

    get("", to=Foo.bar, name="index"),
    get("login", to=Foo.bar, name="login"),
    get("admin"),
    get("foobar/:catchall<path>"),

    scope("/", host="blog.example.com")(
        get("admin"),
        get("foobar/foo", to=Foo.bar),
    ),

    scope("/:locale<en|es>/")(
        get("", to=Foo.bar),
        get(":item_id<int>", to=Foo.bar),
    ),
]


def test_match_domain(app, web):
    app.config["debug"] = True
    app.routes = [
        scope("/", host="example.com")(
            get("/", to=Foo.bar),
        ),
    ]
    resp = web.get("http://example.com/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"


def test_redirect(app, web):
    app.routes = [get("/", redirect="http://example.com")]
    resp = web.get("/")

    assert resp.status == status.temporary_redirect
    assert resp.headers["Location"] == "http://example.com"


def test_url_for(app):
    app.routes = TEST_ROUTES
    assert app.url_for("Items.index") == "/api/items"
    assert app.url_for("Items.create") == "/api/items"
    assert app.url_for("Items.show", item_id=3) == "/api/items/3"
    assert app.url_for("Items.archive", year=2018, month=5) == "/api/items/2018/5"


def test_url_for_object(app):
    app.routes = TEST_ROUTES
    object = Dot({"year": 2018, "month": 5})
    assert app.url_for("Items.archive", object) == "/api/items/2018/5"


def test_url_for_anchor(app):
    app.routes = TEST_ROUTES
    url = app.url_for("login", _anchor="yeah")
    assert url == "/login#yeah"


def test_url_for_missing_param(app):
    app.routes = TEST_ROUTES
    with pytest.raises(MissingParameter):
        app.url_for("Items.archive", year="2018")


def test_url_for_bad_placeholder(app):
    app.routes = TEST_ROUTES
    with pytest.raises(BadPlaceholder):
        app.url_for("Items.archive", year=18, month=-3)


def test_url_for_extra_query(app):
    app.routes = TEST_ROUTES
    url = app.url_for("Items.index", foo="bar")
    assert url == "/api/items?foo=bar"

    url = app.url_for("Items.archive", year=2018, month=5, foo="bar")
    assert url == "/api/items/2018/5?foo=bar"


def test_url_for_not_found(app):
    app.routes = TEST_ROUTES
    with pytest.raises(NameNotFound):
        app.url_for("wtf")
