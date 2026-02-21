"""Minimal end-to-end test — request in, text response out."""

import pytest

from proper import App, status
from proper.controller import Controller
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


class TestHappyPath:
    def test_returns_200(self, app):
        result = app.get("/hello")
        assert result.status == status.ok

    def test_returns_text_body(self, app):
        result = app.get("/hello")
        assert result.body == "hello world"

    def test_path_param_forwarded_to_controller(self, app):
        result = app.get("/hello/alice")
        assert result.status == status.ok
        assert result.body == "hello alice"


def test_to_seconds():
    assert to_seconds(seconds=1) == 1
    assert to_seconds(minutes=1, seconds=3) == 63
    assert to_seconds(hours=1) == 3600
    assert to_seconds(days=1) == 86400
