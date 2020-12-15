import pytest

from proper.constants import GET, POST
from proper.errors import MatchNotFound, MethodNotAllowed
from proper.router import (
    BadPlaceholder,
    MissingParameter,
    NameNotFound,
    Router,
    delete,
    get,
    post,
    scope,
)


@pytest.fixture
def router():
    router = Router()
    router.routes = [
        get("", to="Pages.index", name="index"),
        get("login", to="Pages.login", name="login"),

        scope("/api/")(
            get("items", to="Items.index"),
            get("items/:item_id<int>", to="Items.show"),
            get(r"items/:year<\d{4}>/:month<\d{1,2}>", to="items.archive"),
            post("/items", to="Items.create"),
            delete("/items/:item_id<int>", to="meh"),
        ),

        scope("/foobar/")(
            get("", to="meh"),
            get("foo", to="meh"),
            get("bar", to="meh"),
        ),

        get("foobar/:catchall<path>", to="meh"),
        get("admin", to="meh"),

        scope("/", host="blog.example.com")(
            get("admin", to="meh"),
            get("foobar/foo", to="FooBar.foo"),
        ),

        scope("/:locale<en|es>/")(
            get("", to="localized.index"),
            get(":item_id<int>", to="localized.item"),
        ),
    ]
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
    router.routes = [
        get("meh", to="meh", name="com_host", host="example.com"),
        get("meh", to="meh", name="org_host", host="example.org"),
        get("meh", to="meh", name="default_host"),
    ]

    ro, params = router.match(GET, "/meh")
    assert ro.name == "default_host"

    ro, params = router.match(GET, "/meh", host="example.org")
    assert ro.name == "org_host"

    ro, params = router.match(GET, "/meh", host="example.com")
    assert ro.name == "com_host"


def test_route_without_host_match_any_host(router):
    router.routes = [
        get("a", to="meh", name="a"),
        get("b", to="meh", name="b"),
    ]

    ro, params = router.match(GET, "/a", "jpscaletti.com")
    assert ro.name == "a"
    ro, params = router.match(GET, "/b", "jpscaletti.com")
    assert ro.name == "b"


def test_match_scope_placeholder(router):
    ro, _ = router.match(GET, "/en")
    assert ro.to == "localized.index"

    ro, _ = router.match(GET, "/es/33")
    assert ro.to == "localized.item"


def test_match_mixed_paths(router):
    router.routes = [
        get("books/:section<path>/:title", to="meh")
    ]
    _, params = router.match(GET, "/books/some/section/last-words")
    assert params["section"] == "some/section"
    assert params["title"] == "last-words"

    router.routes = [
        get(":this<path>/is/:madness<path>", to="meh")
    ]
    _, params = router.match(GET, "/a/b/c/d/is/e/f/g")
    assert params["this"] == "a/b/c/d"
    assert params["madness"] == "e/f/g"

    router.routes = [
        get(":super<path>/:bad<path>", to="meh")
    ]
    _, params = router.match(GET, "/a/b/c/d/e/f/g")
    assert params["super"] == "a/b/c/d/e/f"
    assert params["bad"] == "g"


def test_url_for(router):
    assert router.url_for("Items.index") == "/api/items"
    assert router.url_for("Items.create") == "/api/items"
    assert router.url_for("Items.show", item_id=3) == "/api/items/3"
    url = router.url_for("items.archive", year=2018, month=5)
    assert url == "/api/items/2018/5"


def test_url_for_anchor(router):
    url = router.url_for("login", _anchor="success")
    assert url == "/login#success"


def test_url_for_missing_param(router):
    with pytest.raises(MissingParameter):
        router.url_for("items.archive", year="2018")


def test_url_for_bad_param(router):
    with pytest.raises(BadPlaceholder):
        router.url_for("items.archive", year=18, month=-3)


def test_url_for_extra_query(router):
    url = router.url_for("Items.index", foo="bar")
    assert url == "/api/items?foo=bar"

    url = router.url_for("items.archive", year=2018, month=5, foo="bar")
    assert url == "/api/items/2018/5?foo=bar"


def test_url_for_not_found(router):
    with pytest.raises(NameNotFound):
        router.url_for("wtf")


def test_can_only_work_with_routes():
    router = Router()
    router._debug = True
    router.routes = [get("foo", to="bar")]

    with pytest.raises(AssertionError):
        router.routes = [
            get("foo", to="bar"),
            object(),
        ]
