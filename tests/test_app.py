import pytest

from proper import App, TestClient, status
from proper.controller import Controller
from proper.core.config import load_config
from proper.errors import BadSecretKey, ConfigError
from proper.router import Route
from proper.units import to_seconds


class GreetController(Controller):
    def index(self):
        return "hello world"

    def show(self):
        name = self.params.get("name", "stranger")
        return f"hello {name}"

    def options(self):
        return "Custom OPTIONS response"

    def echo_method(self):
        self.response.headers["real"] = self.request.method
        return ""


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App(__name__, config)
    app.router.add_route(Route(method="GET", path="/hello", to=GreetController.index))

    app.router.add_route(Route(method="GET", path="/hello/:name", to=GreetController.show))
    app.router.add_route(Route(method="OPTIONS", path="/hello/:name", to=GreetController.options))

    app.router.add_route(Route(method="GET", path="/echo", to=GreetController.echo_method))
    app.router.add_route(Route(method="POST", path="/echo", to=GreetController.echo_method))
    app.router.add_route(Route(method="PUT", path="/echo", to=GreetController.echo_method))
    app.router.add_route(Route(method="DELETE", path="/echo", to=GreetController.echo_method))
    app.router.add_route(Route(method="PATCH", path="/echo", to=GreetController.echo_method))
    app.router.add_route(Route(method="QUERY", path="/echo", to=GreetController.echo_method))
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_returns_200(client):
    result = client.get("/hello")
    assert result.status == status.ok
    assert result.body == "hello world"


def test_path_param_forwarded_to_controller(client):
    result = client.get("/hello/alice")
    assert result.status == status.ok
    assert result.body == "hello alice"


def test_to_seconds():
    assert to_seconds(seconds=1) == 1
    assert to_seconds(minutes=1, seconds=3) == 63
    assert to_seconds(hours=1) == 3600
    assert to_seconds(days=1) == 86400


def test_empty_secret_keys_raises():
    with pytest.raises(ConfigError, match="SECRET_KEYS list is empty"):
        load_config({"SECRET_KEYS": []})


def test_short_secret_key_raises():
    with pytest.raises(BadSecretKey, match="not secure enough"):
        load_config({"SECRET_KEYS": ["tooshort"]})


def test_invalid_samesite_raises():
    with pytest.raises(ConfigError, match="SESSION_COOKIE_SAMESITE"):
        load_config({
            "SECRET_KEYS": ["*" * 50],
            "SESSION_COOKIE_SAMESITE": "Invalid",
        })


def test_load_config_from_class():
    class MyConfig:
        SECRET_KEYS = ["*" * 50]
        DEBUG = True

    config = load_config(MyConfig)
    assert config.SECRET_KEYS == ["*" * 50]
    assert config.DEBUG is True


def test_method_override(client):
    # Test overriding POST to PUT
    result = client.post("/echo", headers={"X-HTTP-Method-Override": "PUT"})
    assert result.headers["real"] == "PUT"

    # Test overriding POST to DELETE
    result = client.post("/echo", headers={"X-HTTP-Method-Override": "DELETE"})
    assert result.headers["real"] == "DELETE"

    # Test overriding POST to PATCH
    result = client.post("/echo", headers={"X-HTTP-Method-Override": "PATCH"})
    assert result.headers["real"] == "PATCH"

    # Test overriding POST to QUERY
    result = client.post("/echo", headers={"X-HTTP-Method-Override": "QUERY"})
    assert result.headers["real"] == "QUERY"


def test_method_does_not_override(client):
    result = client.put("/echo", headers={"X-HTTP-Method-Override": "DELETE"})
    assert result.headers["real"] == "PUT"

    # Test GET does not override
    result = client.get("/echo", headers={"X-HTTP-Method-Override": "PUT"})
    assert result.headers["real"] == "GET"

    # Test HEAD does not override
    result = client.head("/echo", headers={"X-HTTP-Method-Override": "PUT"})
    assert result.headers["real"] == "GET"


def test_method_not_allowed_returns_allow_header(client):
    result = client.post("/hello")
    assert result.status == status.method_not_allowed
    assert "Allow" in result.headers
    assert result.headers["Allow"] == "GET, HEAD"


def test_custom_options_response(client):
    result = client.options("/hello/world")
    assert result.status == status.ok
    assert result.body == "Custom OPTIONS response"


def test_head_returns_same_headers(client):
    get_result = client.get("/hello")
    head_result = client.head("/hello")
    assert head_result.status == get_result.status
    assert head_result.headers.items() == get_result.headers.items()
    assert head_result.body == ""
