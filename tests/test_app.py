"""Minimal end-to-end test — request in, text response out."""

import pytest

from proper import App, status
from proper.config import load_config
from proper.controller import Controller
from proper.errors import BadSecretKey, ConfigError
from proper.router import Route
from proper.units import to_seconds


class GreetController(Controller):
    def index(self):
        return "hello world"

    def show(self):
        name = self.params.get("name", "stranger")
        return f"hello {name}"


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App("tests", config)
    app.router.add_route(Route(method="GET", path="/hello", to=GreetController.index))
    app.router.add_route(Route(method="GET", path="/hello/:name", to=GreetController.show))
    return app


def test_returns_200(app):
    result = app.get("/hello")
    assert result.status == status.ok
    assert result.body == "hello world"


def test_path_param_forwarded_to_controller(app):
    result = app.get("/hello/alice")
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
