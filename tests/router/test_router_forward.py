import pytest

from proper.router import forward


def wsgi_app(environ, start_response):
    pass


def test_forward_defaults():
    fw = forward("/dashboard", wsgi_app)

    assert fw.path == "/dashboard"
    assert fw.forward_to == wsgi_app


@pytest.mark.parametrize(
    "path, expected",
    [
        ("", "/"),
        ("api", "/api"),
        ("/api", "/api"),
        ("api/", "/api"),
        ("/api/", "/api"),
    ],
)
def test_forward_must_add_slashes_to_path(path, expected):
    assert forward(path, wsgi_app).path == expected


def test_scope_repr():
    assert str(forward("", wsgi_app)) == "<route FORWARD / “wsgi_app”>"
    assert str(forward("api", wsgi_app)) == "<route FORWARD /api “wsgi_app”>"


def test_forward_must_be_callable():
    with pytest.raises(AssertionError):
        forward("/dashboard/", "?")
