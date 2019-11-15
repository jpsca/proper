import pytest

from proper.constants import DELETE
from proper.constants import GET
from proper.constants import OPTIONS
from proper.constants import PATCH
from proper.constants import POST
from proper.constants import PUT
from proper.router import delete
from proper.router import get
from proper.router import options
from proper.router import patch
from proper.router import post
from proper.router import put
from proper.router import route
from proper.router.router_errors import BadParameter
from proper.router.router_errors import BadRule
from proper.router.router_errors import MissingParameter


def test_route_defaults():
    r = get("foobar", to="something")
    assert r.method == GET
    assert r.path == "/foobar"
    assert r.to == "something"
    assert r.name == "something"
    assert r.redirect is None

    r = get("foobar/", to="")
    assert r.path == "/foobar"

    assert get("foobar/", to="") == get("foobar", to="")
    assert get("foobar", to="") != get("/", to="")
    assert get("foobar", to="") != object()


def test_route_must_have_to_redirect_or_forward():
    with pytest.raises(AssertionError):
        get("foobar")


def test_route_repr():
    assert str(get("foobar", to="")) == "<route GET /foobar>"


def test_route_shortcuts():
    get("/", to="").method == GET
    post("/", to="").method == POST
    put("/", to="").method == PUT
    delete("/", to="").method == DELETE
    options("/", to="").method == OPTIONS
    patch("/", to="").method == PATCH


def test_route_must_have_method_and_path():
    with pytest.raises(Exception):
        route()

    with pytest.raises(Exception):
        route(GET)

    with pytest.raises(Exception):
        get()


class TestController(object):
    def method(self):
        pass


def test_route_name_is_set():
    r = get("/", to="Pages.method", name="hello")
    assert r.name == "hello"

    r = get("/", to="Pages.method")
    assert r.name == "Pages.method"

    r = get("/", name="hello", redirect="/blog/")
    assert r.name == "hello"

    r = get("/", to=TestController.method)
    assert r.name == "TestController.method"

    r = get("/", to="TestController.method")
    assert r.name == "TestController.method"

    r = get("/", to="")
    assert r.name == ""


def test_invalid_route_rule():
    with pytest.raises(BadRule):
        get(":a", to="", rules={"a": r"{1["}).compile_path()


def test_default_route_rule():
    rx = get(":a", to="").compile_path()
    assert rx.match("/hola")
    assert rx.match("/h-o.l_a")
    assert rx.match("/1234")
    assert rx.match("/3.1415")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert not rx.match("/hola/mundo")


def test_route_path_pattern():
    rx = get(":a", to="", rules={"a": "path"}).compile_path()
    assert rx.match("/hola/mundo")
    assert rx.match("/hola")
    assert rx.match("/hola/../mundo")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert rx.match("/hola.com/mundo")


def test_route_int_pattern():
    rx = get(":a", to="", rules={"a": "int"}).compile_path()
    assert rx.match("/1")
    assert rx.match("/4567")
    assert not rx.match("/45hola67")


def test_route_float_pattern():
    rx = get(":a", to="", rules={"a": "float"}).compile_path()
    assert rx.match("/3.14159")
    assert rx.match("/0.6")
    assert not rx.match("/1984")
    assert not rx.match("/1984.")
    assert not rx.match("/.6")
    assert not rx.match("/45hola67")


def test_route_format():
    route = get(":year/:month", to="", rules={"year": r"\d{4}", "month": r"\d{1,2}"})
    assert route.format(year="2018", month="05") == "/2018/05"


def test_route_format_static():
    route = get("/", to="")
    assert route.format() == "/"

    route = get("/iopenat/theclose", to="")
    assert route.format() == "/iopenat/theclose"


def test_route_format_params_to_strings():
    route = get(":year/:month", to="", rules={"year": r"\d{4}", "month": r"\d{1,2}"})
    assert route.format(year=2018, month=5) == "/2018/5"


def test_route_format_missing_param():
    route = get(":year/:month", to="", rules={"year": r"\d{4}", "month": r"\d{1,2}"})
    with pytest.raises(MissingParameter):
        route.format(year="2018")


def test_route_format_bad_param():
    route = get(":year/:month", to="", rules={"year": r"\d{4}", "month": r"\d{1,2}"})
    with pytest.raises(BadParameter):
        route.format(year="18", month="10")


def test_route_format_query():
    route = get("/", to="")
    assert route.format(a="Dirk", b="Gently") == "/?a=Dirk&b=Gently"

    route = get(":year/:month", to="", rules={"year": r"\d{4}", "month": r"\d{1,2}"})
    assert route.format(year=2018, month=5, foo="bar") == "/2018/5?foo=bar"
