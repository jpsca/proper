"""Which pages may open a WebSocket to the app."""
import pytest

from proper.channels import allowed_origins, origin_allowed


CONFIG = {"HOST": "app.example", "PORT": 2300, "DEBUG": False, "CABLE_ALLOWED_ORIGINS": []}


@pytest.mark.parametrize("origin, host, allowed", [
    (None, "app.example", True),  # not a browser
    ("", "app.example", True),
    ("https://app.example", "app.example", True),  # the Host it connected to
    ("https://APP.example/", "app.example", True),
    ("https://app.example", "proxy.internal:4391", True),  # the app's HOST
    ("https://evil.example", "app.example", False),
    ("http://app.example.evil.example", "app.example", False),
    ("null", "app.example", False),  # sandboxed iframe, file://
    ("http://localhost:2300", "localhost:2301", False),  # another port, outside DEBUG
])
def test_origin_allowed(origin, host, allowed):
    assert origin_allowed(origin, host, CONFIG) is allowed


def test_listed_origins_are_allowed():
    config = {**CONFIG, "CABLE_ALLOWED_ORIGINS": ["https://admin.example/"]}
    assert origin_allowed("https://admin.example", "app.example", config)


def test_in_debug_any_port_of_the_host_is_allowed():
    config = {**CONFIG, "DEBUG": True}
    assert origin_allowed("http://localhost:2300", "localhost:2301", config)
    assert not origin_allowed("http://elsewhere:2300", "localhost:2301", config)


def test_allowed_origins_as_a_list():
    assert allowed_origins(CONFIG) == ["http://app.example", "https://app.example"]
    config = {**CONFIG, "DEBUG": True, "HOST": "localhost:2300",
              "CABLE_ALLOWED_ORIGINS": ["https://admin.example", "http://localhost:2300"]}
    assert allowed_origins(config) == [
        "https://admin.example", "http://localhost:2300",
        "https://localhost:2300", "http://127.0.0.1:2300",
    ]
    assert allowed_origins({}) == []
