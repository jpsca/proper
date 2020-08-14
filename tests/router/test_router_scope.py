import pytest

from proper.router import get, scope


def test_scope_defaults():
    s = scope("/")
    assert s.mount == "/"


@pytest.mark.parametrize(
    "mount, expected",
    [
        ("", "/"),
        ("api", "/api"),
        ("/api", "/api"),
        ("api/", "/api"),
        ("/api/", "/api"),
    ],
)
def test_scope_must_add_slashes_to_mount(mount, expected):
    assert scope(mount).mount == expected


def test_scope_repr():
    assert str(scope("")) == "<scope />"
    assert str(scope("api")) == "<scope /api>"


def test_scope_must_have_mount():
    with pytest.raises(Exception):
        scope()


def test_scope_mount_routes_static():
    routes = scope("/", host="example.com")(get("api", to="meh"))
    route = routes[0]
    assert route.path == "/api"
    assert route.host == "example.com"


def test_scope_mount_empty_path():
    routes = scope("/foobar/")(
        get("", to="")
    )
    assert routes[0].path == "/foobar"
