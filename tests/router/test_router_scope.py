import pytest

from proper.router import get
from proper.router import scope


def test_scope_defaults():
    s = scope("/")
    assert s.mount == "/"
    assert s.pipeline == ()

    s = scope("api", pipeline=[1, 2, 4])
    assert s.mount == "/api"
    assert s.pipeline == [1, 2, 4]


@pytest.mark.parametrize("mount, expected", [
    ("", "/"),
    ("api", "/api"),
    ("/api", "/api"),
    ("api/", "/api"),
    ("/api/", "/api"),
])
def test_scope_must_add_slashes_to_mount(mount, expected):
    assert scope(mount).mount == expected


def test_scope_repr():
    assert str(scope("")) == "<scope />"
    assert str(scope("api")) == "<scope /api>"


def test_scope_must_have_mount():
    with pytest.raises(Exception):
        scope()


def test_scope_mount_routes_static():
    pipeline = [1, 2, 3]
    routes = scope("/", host="example.com", pipeline=pipeline)(
        get("api", to="meh")
    )
    route = routes[0]
    assert route.path == "/api"
    assert route.host == "example.com"
    assert route.pipeline == pipeline


def test_scope_mount_routes_with_placeholders():
    routes = scope("/:year/", rules={"year": "[0-9]{4}"})(
        get("/:title-:id", to="meh", rules={"id": "[0-9]"})
    )
    route = routes[0]
    assert route.path == "/:year/:title-:id"
    assert sorted(route.rules.keys()) == ["id", "title", "year"]
