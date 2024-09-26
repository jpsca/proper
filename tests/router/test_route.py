import pytest

from proper import Controller
from proper.constants import DELETE, GET, OPTIONS, PATCH, POST, PUT
from proper.errors import (
    BadRouteFormat,
    BadRoutePlaceholder,
    MissingRouteParameter,
)
from proper.router import Route


class PagesController(Controller):
    def index(self):
        return "Hello World!"


def test_route_defaults():
    ro = Route(GET, "foobar", to=PagesController.index)
    assert ro.method == GET
    assert ro.path == "/foobar"
    assert ro.to == PagesController.index
    assert ro.name == "PagesController.index"
    assert ro.redirect is None

    ro = Route(GET, "foobar/")
    assert ro.path == "/foobar"

    assert Route(GET, "foobar/") == Route(GET, "foobar")
    assert Route(GET, "foobar") != Route(GET, "/")
    assert Route(GET, "foobar") != object()


def test_route_repr():
    assert str(Route(GET, "foobar")) == "<route GET /foobar>"


def test_route_shortcuts():
    assert Route(GET, "/").method == GET
    assert Route(POST, "/").method == POST
    assert Route(PUT, "/").method == PUT
    assert Route(DELETE, "/").method == DELETE
    assert Route(OPTIONS, "/").method == OPTIONS
    assert Route(PATCH, "/").method == PATCH


def test_route_must_have_method_and_path():
    with pytest.raises(TypeError):
        Route()

    with pytest.raises(TypeError):
        Route(GET)

    with pytest.raises(TypeError):
        Route(GET, )


class AppView:
    def method(self):
        pass


def test_route_name_is_set():
    ro = Route(GET, "/", to=AppView.method, name="hello")
    assert ro.name == "hello"

    ro = Route(GET, "/", to=AppView.method)
    assert ro.name == "AppView.method"

    ro = Route(GET, "/", name="hello", redirect="/blog/")
    assert ro.name == "hello"

    ro = Route(GET, "/")
    assert ro.name is None


def test_invalid_route_format():
    with pytest.raises(BadRouteFormat):
        Route(GET, ":a<{1[>")


def test_default_route_format():
    ro = Route(GET, ":a")
    rx = ro.path_re

    assert rx
    assert rx.match("/hola")
    assert rx.match("/h-o.l_a")
    assert rx.match("/1234")
    assert rx.match("/3.1415")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert not rx.match("/hola/mundo")


def test_route_path_pattern():
    ro = Route(GET, ":a<path>")
    rx = ro.path_re

    assert rx
    assert rx.match("/hola/mundo")
    assert rx.match("/hola")
    assert rx.match("/hola/../mundo")
    assert rx.match("/juanpablo@jpscaletti.com")
    assert rx.match("/hola.com/mundo")


def test_route_int_pattern():
    ro = Route(GET, ":a<int>")
    rx = ro.path_re

    assert rx
    assert rx.match("/1")
    assert rx.match("/4567")
    assert not rx.match("/45hola67")


def test_route_float_pattern():
    ro = Route(GET, ":a<float>")
    rx = ro.path_re

    assert rx
    assert rx.match("/3.14159")
    assert rx.match("/0.6")
    assert not rx.match("/1984")
    assert not rx.match("/1984.")
    assert not rx.match("/.6")
    assert not rx.match("/45hola67")


def test_route_format():
    route = Route(GET, r":year<\d{4}>/:month<\d{2}>")
    assert route.format(year="2018", month="05") == "/2018/05"


def test_route_format_static():
    route = Route(GET, "/")
    assert route.format() == "/"

    route = Route(GET, "/iopenat/theclose")
    assert route.format() == "/iopenat/theclose"


def test_route_format_params_to_strings():
    route = Route(GET, r":year<\d{4}>/:month<\d{1,2}>")
    assert route.format(year=2018, month=5) == "/2018/5"


def test_route_format_missing_param():
    route = Route(GET, r":year<\d{4}>/:month<\d{1,2}>")
    with pytest.raises(MissingRouteParameter):
        route.format(year="2018")


def test_route_format_bad_placeholder():
    route = Route(GET, r":year<\d{4}>/:month<\d{1,2}>")
    with pytest.raises(BadRoutePlaceholder):
        route.format(year="18", month="10")


def test_route_format_query():
    route = Route(GET, "/")
    assert route.format(a="Dirk", b="Gently") == "/?a=Dirk&b=Gently"

    route = Route(GET, r":year<\d{4}>/:month<\d{1,2}>")
    assert route.format(year=2018, month=5, foo="bar") == "/2018/5?foo=bar"
