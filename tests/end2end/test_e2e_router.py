import pytest

from proper import BadParameter
from proper import delete
from proper import get
from proper import MissingParameter
from proper import NameNotFound
from proper import post
from proper import scope
from proper import status


TEST_ROUTES = [
    scope("/api/")(
        get("items", to="Items.index"),
        get("items/:item_id", to="Items.show", rules={"item_id": "int"}),
        get(
            "items/:year/:month",
            to="items.archive",
            rules={"year": r"\d{4}", "month": r"\d{1,2}"},
        ),
        post("/items", to="Items.create"),
        delete("/items/:item_id", to="", rules={"item_id": "int"}),
    ),
    scope("/foobar/")(get("", to=""), get("foo", to=""), get("bar", to=""),),
    scope("/")(
        get("", to="Pages.index", name="index"),
        get("login", to="Pages.login", name="login"),
        get("admin", to=""),
        get("foobar/:catchall", to="", rules={"catchall": "path"}),
    ),
    scope("/", host="blog.example.com")(
        get("admin", to=""), get("foobar/foo", to="FooBar.foo"),
    ),
    scope("/:locale/", rules={"locale": r"(en|es)"})(
        get("", to="localized.index"),
        get(":item_id", to="localized.item", rules={"item_id": "int"}),
    ),
]


def test_match_domain(app, web):
    app.config["debug"] = True
    app.routes = [
        scope("/", host="example.com")(get("/", to="Pages.index"),),
    ]
    resp = web.get("http://example.com/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"


def test_redirect(app, web):
    app.routes = [scope("/")(get("/", redirect="http://example.com"))]
    resp = web.get("/")

    assert resp.status == status.temporary_redirect
    assert resp.headers["Location"] == "http://example.com"


def test_url_for(app):
    app.routes = TEST_ROUTES
    assert app.url_for("Items.index") == "/api/items"
    assert app.url_for("Items.create") == "/api/items"
    assert app.url_for("Items.show", item_id=3) == "/api/items/3"
    url = app.url_for("items.archive", year=2018, month=5)
    assert url == "/api/items/2018/5"


def test_url_for_anchor(app):
    app.routes = TEST_ROUTES
    url = app.url_for("login", _anchor="yeah")
    assert url == "/login#yeah"


def test_url_for_external(app):
    app.routes = TEST_ROUTES
    url = app.url_for("login", _external=True)
    assert url == "http://0.0.0.0:3030/login"


def test_url_for_external_with_ssl(app):
    app.setup({"use_ssl": True})
    app.routes = TEST_ROUTES
    url = app.url_for("login", _external=True)
    assert url == "https://0.0.0.0:3030/login"


def test_url_for_missing_param(app):
    app.routes = TEST_ROUTES
    with pytest.raises(MissingParameter):
        app.url_for("items.archive", year="2018")


def test_url_for_bad_param(app):
    app.routes = TEST_ROUTES
    with pytest.raises(BadParameter):
        app.url_for("items.archive", year=18, month=-3)


def test_url_for_extra_query(app):
    app.routes = TEST_ROUTES
    url = app.url_for("Items.index", foo="bar")
    assert url == "/api/items?foo=bar"

    url = app.url_for("items.archive", year=2018, month=5, foo="bar")
    assert url == "/api/items/2018/5?foo=bar"


def test_url_for_not_found(app):
    app.routes = TEST_ROUTES
    with pytest.raises(NameNotFound):
        app.url_for("wtf")
