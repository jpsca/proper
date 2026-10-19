import traceback

import pytest

from proper import TestClient, status
from proper.controller import Controller
from proper.errors import HTTPError, NotFound
from proper.router import Route


class BoomController(Controller):
    def boom(self):
        raise ValueError("boom")

    def missing(self):
        raise NotFound("no such thing")

    def unavailable(self):
        raise HTTPError("down", status=status.service_unavailable)


class ConflictPageController(Controller):
    def handle(self):
        self.response.status = status.conflict
        self.response.body = "conflict page"


@pytest.fixture()
def app(app):
    app.router.add_route(Route(method="GET", path="boom", to=BoomController.boom))
    app.router.add_route(Route(method="GET", path="missing", to=BoomController.missing))
    app.router.add_route(
        Route(method="GET", path="unavailable", to=BoomController.unavailable)
    )
    return app


def test_an_error_of_the_app_is_raised_in_the_test(app):
    client = TestClient(app)

    with pytest.raises(ValueError, match="boom") as excinfo:
        client.get("/boom")

    # The traceback reaches the line of the controller that raised it
    frames = traceback.extract_tb(excinfo.value.__traceback__)
    assert any(frame.name == "boom" for frame in frames)


def test_the_error_page_when_not_raising(app):
    client = TestClient(app, raise_server_errors=False)

    response = client.get("/boom")

    assert response.status == status.server_error


def test_raising_can_be_turned_off_after_creating_the_client(app):
    client = TestClient(app)
    client.raise_server_errors = False

    response = client.get("/boom")

    assert response.status == status.server_error


def test_an_http_error_is_answered_not_raised(app):
    client = TestClient(app)

    assert client.get("/missing").status == status.not_found
    assert client.get("/unavailable").status == status.service_unavailable


def test_an_error_that_a_handler_answers_without_a_server_error_is_not_raised(app):
    app.router.add_error_handler(ValueError, ConflictPageController.handle)
    client = TestClient(app)

    response = client.get("/boom")

    assert response.status == status.conflict
    assert response.body == "conflict page"
