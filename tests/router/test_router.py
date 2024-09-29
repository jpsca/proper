import pytest

from proper import Controller
from proper.constants import GET, POST
from proper.errors import (
    BadRoutePlaceholder,
    MatchNotFound,
    MethodNotAllowed,
    MissingRouteParameter,
    RouteNotFound,
)
from proper.router import Route, Router


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


class Localized(Controller):
    def index(self):
        return "Localized index"

    def item(self, item_id):
        return f"Localized {item_id}"


@pytest.fixture
def router():
    router = Router()
    router.get("", name="index")(FooController.bar)
    router.get("login", name="login")(FooController.bar)

    router.get("foobar")(FooController.bar)
    router.get("foobar/foo")(FooController.bar)
    router.get("foobar/bar")(FooController.bar)
    router.get("foobar/:catchall<path>")(FooController.bar)
    router.get("foobar/foo", host="blog.example.com")(FooController.bar)

    router.get("admin")(FooController.bar)
    router.get("admin", host="blog.example.com")(FooController.bar)

    router.get("api/items")(ItemsController.index)
    router.post("api/items")(ItemsController.create)
    router.get("api/items/:item_id<int>")(ItemsController.show)
    router.get(r"api/items/:year<\d{4}>/:month<\d{1,2}>")(ItemsController.archive)

    router.get(":locale<en|es>")(Localized.index)
    router.get(":locale<en|es>/:item_id<int>")(Localized.item)

    for route in router.routes:
        print(route)
    return router


def test_match(router):
    ro, params = router.match(GET, "/")
    assert ro.method == GET
    assert ro.path == "/"
    assert ro.name == "index"
    assert params == {}

    ro, params = router.match(GET, "/foobar")
    assert ro.path == "/foobar"
    ro, params = router.match(GET, "/foobar/")
    assert ro.path == "/foobar"

    ro, params = router.match(GET, "/api/items")
    assert ro.path == "/api/items"


def test_match_not_found(router):
    with pytest.raises(MatchNotFound):
        router.match(GET, "/wtf")


def test_method_not_allowed(router):
    with pytest.raises(MethodNotAllowed):
        router.match(POST, "/")


def test_match_placeholders(router):
    ro, params = router.match(GET, "/api/items/2018/10")
    assert ro.method == GET
    assert ro.path == r"/api/items/:year<\d{4}>/:month<\d{1,2}>"
    # Note how the numbers aren't converted to integers
    assert params == {"year": "2018", "month": "10"}

    with pytest.raises(MatchNotFound):
        router.match(GET, "/api/items/18/100")


def test_try_with_the_next_scope(router):
    ro, params = router.match(GET, "/foobar/awesome")
    assert ro.path == "/foobar/:catchall<path>"
    assert params == {"catchall": "awesome"}

    ro, params = router.match(GET, "/foobar/everything/is/awesome")
    assert ro.path == "/foobar/:catchall<path>"
    assert params == {"catchall": "everything/is/awesome"}


def test_match_host(router):
    router._routes = [
        Route(method=GET, path="meh", to=FooController.bar, name="com_host", host="example.com"),
        Route(method=GET, path="meh", to=FooController.bar, name="org_host", host="example.org"),
        Route(method=GET, path="meh", to=FooController.bar, name="default_host"),
    ]

    ro, params = router.match(GET, "/meh")
    assert ro.name == "default_host"

    ro, params = router.match(GET, "/meh", host="example.org")
    assert ro.name == "org_host"

    ro, params = router.match(GET, "/meh", host="example.com")
    assert ro.name == "com_host"


def test_route_without_host_match_any_host(router):
    router._routes = [
        Route(method=GET, path="a", to=FooController.bar, name="a"),
        Route(method=GET, path="b", to=FooController.bar, name="b"),
    ]

    ro, params = router.match(GET, "/a", "jpscaletti.com")
    assert ro.name == "a"
    ro, params = router.match(GET, "/b", "jpscaletti.com")
    assert ro.name == "b"


def test_match_scope_placeholder(router):
    ro, _ = router.match(GET, "/en")
    assert ro.to == Localized.index

    ro, _ = router.match(GET, "/es/33")
    assert ro.to == Localized.item


def test_match_mixed_paths(router):
    router._routes = [
        Route(method=GET, path="books/:section<path>/:title", to=FooController.bar)
    ]
    _, params = router.match(GET, "/books/some/section/last-words")
    assert params["section"] == "some/section"
    assert params["title"] == "last-words"

    router._routes = [
        Route(method=GET, path=":this<path>/is/:madness<path>", to=FooController.bar)
    ]
    _, params = router.match(GET, "/a/b/c/d/is/e/f/g")
    assert params["this"] == "a/b/c/d"
    assert params["madness"] == "e/f/g"

    router._routes = [
        Route(method=GET, path=":super<path>/:bad<path>", to=FooController.bar)
    ]
    _, params = router.match(GET, "/a/b/c/d/e/f/g")
    assert params["super"] == "a/b/c/d/e/f"
    assert params["bad"] == "g"


def test_url_for(router):
    assert router.url_for("Items.index") == "/api/items"
    assert router.url_for("Items.create") == "/api/items"
    assert router.url_for("Items.show", item_id=3) == "/api/items/3"
    url = router.url_for("Items.archive", year=2018, month=5)
    assert url == "/api/items/2018/5"


def test_url_for_anchor(router):
    url = router.url_for("login", _anchor="success")
    assert url == "/login#success"


def test_url_for_missing_param(router):
    with pytest.raises(MissingRouteParameter):
        router.url_for("Items.archive", year="2018")


def test_url_for_bad_param(router):
    with pytest.raises(BadRoutePlaceholder):
        router.url_for("Items.archive", year=18, month=-3)


def test_url_for_extra_query(router):
    url = router.url_for("Items.index", foo="bar")
    assert url == "/api/items?foo=bar"

    url = router.url_for("Items.archive", year=2018, month=5, foo="bar")
    assert url == "/api/items/2018/5?foo=bar"


def test_url_for_not_found(router):
    with pytest.raises(RouteNotFound):
        router.url_for("wtf")
