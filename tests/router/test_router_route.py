import pytest

from proper.constants import DELETE, GET, OPTIONS, PATCH, POST, PUT
from proper.router import (
    BadFormat,
    BadPlaceholder,
    MissingParameter,
    delete,
    get,
    options,
    patch,
    post,
    put,
    Route,
)


def test_route_defaults(Pages):
    r = get("foobar", to=Pages.index)
    assert r.method == GET
    assert r.path == "/foobar"
    assert r.to == Pages.index
    assert r.name == "_Pages.index"
    assert r.redirect is None

    r = get("foobar/")
    assert r.path == "/foobar"

    assert get("foobar/") == get("foobar")
    assert get("foobar") != get("/")
    assert get("foobar") != object()


def test_route_repr():
    assert str(get("foobar")) == "<route GET /foobar>"


def test_route_shortcuts():
    assert get("/").method == GET
    assert post("/").method == POST
    assert put("/").method == PUT
    assert delete("/").method == DELETE
    assert options("/").method == OPTIONS
    assert patch("/").method == PATCH


def test_route_must_have_method_and_path():
    with pytest.raises(Exception):
        Route()

    with pytest.raises(Exception):
        Route(GET)

    with pytest.raises(Exception):
        get()


class TestController:
    def method(self):
        pass


def test_route_name_is_set():
    r = get("/", to=TestController.method, name="hello")
    assert r.name == "hello"

    r = get("/", to=TestController.method)
    assert r.name == "TestController.method"

    r = get("/", name="hello", redirect="/blog/")
    assert r.name == "hello"

    r = get("/")
    assert r.name is None


def test_invalid_route_format():
    with pytest.raises(BadFormat):
        ro = get(":a<{1[>")
        ro.compile_path()


def test_default_route_format():
    ro = get(":a")
    ro.compile_path()
    rx = ro.path_re
    assert rx.match("/hola")
    assert rx.match("/h-o.l_a")
    assert rx.match("/1234")
    assert rx.match("/3.1415")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert not rx.match("/hola/mundo")


def test_route_path_pattern():
    ro = get(":a<path>")
    ro.compile_path()
    rx = ro.path_re
    assert rx.match("/hola/mundo")
    assert rx.match("/hola")
    assert rx.match("/hola/../mundo")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert rx.match("/hola.com/mundo")


def test_route_int_pattern():
    ro = get(":a<int>")
    ro.compile_path()
    rx = ro.path_re
    assert rx.match("/1")
    assert rx.match("/4567")
    assert not rx.match("/45hola67")


def test_route_float_pattern():
    ro = get(":a<float>")
    ro.compile_path()
    rx = ro.path_re
    assert rx.match("/3.14159")
    assert rx.match("/0.6")
    assert not rx.match("/1984")
    assert not rx.match("/1984.")
    assert not rx.match("/.6")
    assert not rx.match("/45hola67")


def test_route_format():
    route = get(r":year<\d{4}>/:month<\d{2}>")
    assert route.format(year="2018", month="05") == "/2018/05"


def test_route_format_static():
    route = get("/")
    assert route.format() == "/"

    route = get("/iopenat/theclose")
    assert route.format() == "/iopenat/theclose"


def test_route_format_params_to_strings():
    route = get(r":year<\d{4}>/:month<\d{1,2}>")
    assert route.format(year=2018, month=5) == "/2018/5"


def test_route_format_missing_param():
    route = get(r":year<\d{4}>/:month<\d{1,2}>")
    with pytest.raises(MissingParameter):
        route.format(year="2018")


def test_route_format_bad_placeholder():
    route = get(r":year<\d{4}>/:month<\d{1,2}>")
    with pytest.raises(BadPlaceholder):
        route.format(year="18", month="10")


def test_route_format_query():
    route = get("/")
    assert route.format(a="Dirk", b="Gently") == "/?a=Dirk&b=Gently"

    route = get(r":year<\d{4}>/:month<\d{1,2}>")
    assert route.format(year=2018, month=5, foo="bar") == "/2018/5?foo=bar"
