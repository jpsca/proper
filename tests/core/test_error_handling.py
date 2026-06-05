from unittest.mock import MagicMock, patch

import pytest

from proper import App, TestClient, status
from proper.controller import Controller
from proper.core.request import Request
from proper.core.response import Response
from proper.errors import (
    Forbidden,
    MatchNotFound,
    MethodNotAllowed,
    NotFound,
)
from proper.helpers.asgi import make_test_scope
from proper.router import Route


def _make_request(**kw):
    return Request(make_test_scope(**kw))


def _make_response(*, app=None, **kw):
    scope = make_test_scope(**kw)
    if app is not None:
        scope["app"] = app
    return Response(scope)


# --- module-level controllers (required by pipeline.dispatch) ---


class _ExplodingController(Controller):
    def index(self):
        raise ValueError("boom")


class _ForbiddenController(Controller):
    def index(self):
        raise Forbidden("denied")


class _NotFoundController(Controller):
    def index(self):
        raise NotFound("missing")


class _OkController(Controller):
    def index(self):
        return "ok"


class _ErrorPageController(Controller):
    def handle(self):
        self.response.body = "custom error page"


class _CatchAllErrorPageController(Controller):
    def handle(self):
        self.response.body = "caught"


# --- Fixtures ---


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        "CATCH_ALL_ERRORS": True,
    }
    return App(__name__, config)


@pytest.fixture()
def client(app):
    return TestClient(app)



class TestHandleAppError:
    """Tests for App._handle_app_error dispatch logic."""

    def test_sets_status_from_http_error(self, app):
        request = _make_request()
        response = _make_response()
        response.error = NotFound("gone")
        app._handle_app_error(request, response)
        assert response.status == status.not_found

    def test_generic_exception_gets_server_error_status(self, app):
        request = _make_request()
        response = _make_response()
        response.error = ValueError("oops")
        app._handle_app_error(request, response)
        assert response.status == status.server_error

    def test_debug_mode_skips_custom_handlers(self, app):
        app.debug = True

        app.router.add_error_handler(ValueError, _ErrorPageController.handle)

        request = _make_request()
        response = _make_response()
        response.error = ValueError("oops")

        with patch("proper.app.debug_error_handler"):
            app._handle_app_error(request, response)

        assert response.body != "custom error page"

    def test_custom_handler_called_for_matching_error(self, app):
        app.router.add_error_handler(ValueError, _ErrorPageController.handle)

        request = _make_request()
        response = _make_response(app=app)
        response.error = ValueError("bad value")
        app._handle_app_error(request, response)
        assert response.body == "custom error page"

    def test_custom_handler_matches_subclass(self, app):
        """A handler for Exception should catch ValueError."""
        app.router.add_error_handler(Exception, _CatchAllErrorPageController.handle)

        request = _make_request()
        response = _make_response(app=app)
        response.error = ValueError("sub")
        app._handle_app_error(request, response)
        assert response.body == "caught"

    def test_falls_back_to_default_when_no_custom_match(self, app):
        # Register handler for TypeError only
        app.router.add_error_handler(TypeError, _ErrorPageController.handle)

        request = _make_request()
        response = _make_response(app=app)
        response.error = ValueError("no match")
        app._handle_app_error(request, response)
        assert response.body != "custom error page"



class TestDefaultErrorHandler:
    def test_debug_mode_calls_debug_handler(self, app):
        app.debug = True
        request = _make_request()
        response = _make_response()
        response.error = ValueError("boom")

        with patch("proper.app.debug_error_handler") as mock_debug:
            app._default_error_handler(request, response)
            mock_debug.assert_called_once_with(app, request, response)

    def test_production_catch_all_calls_fallback(self, app):
        request = _make_request()
        response = _make_response()
        response.error = ValueError("boom")

        with patch("proper.app.fallback_error_handler") as mock_fallback:
            app._default_error_handler(request, response)
            mock_fallback.assert_called_once_with(response)

    def test_production_no_catch_all_reraises(self, app):
        app.config.CATCH_ALL_ERRORS = False
        request = _make_request()
        response = _make_response()

        with pytest.raises(ValueError, match="boom"):
            try:
                raise ValueError("boom")
            except ValueError as exc:
                response.error = exc
                app._default_error_handler(request, response)

    def test_sets_status_from_error_attribute(self, app):
        request = _make_request()
        response = _make_response()
        response.error = Forbidden("denied")

        with patch("proper.app.fallback_forbidden_handler"):
            app._default_error_handler(request, response)

        assert response.status == status.forbidden

    def test_sets_server_error_for_generic_exception(self, app):
        request = _make_request()
        response = _make_response()
        response.error = RuntimeError("crash")

        with patch("proper.app.fallback_error_handler"):
            app._default_error_handler(request, response)

        assert response.status == status.server_error



class TestDefaultErrorHandlerDebug:
    def test_match_not_found_uses_not_found_handler(self, app):
        request = _make_request()
        response = _make_response()
        response.error = MatchNotFound("no route")

        with patch("proper.app.debug_not_found_handler") as mock_handler:
            app._default_error_handler_debug(request, response)
            mock_handler.assert_called_once_with(app, request, response)

    def test_method_not_allowed_uses_not_found_handler(self, app):
        request = _make_request()
        response = _make_response()
        response.error = MethodNotAllowed("nope", allowed=["GET"])

        with patch("proper.app.debug_not_found_handler") as mock_handler:
            app._default_error_handler_debug(request, response)
            mock_handler.assert_called_once_with(app, request, response)

    def test_other_error_uses_error_handler(self, app):
        request = _make_request()
        response = _make_response()
        response.error = ValueError("oops")

        with patch("proper.app.debug_error_handler") as mock_handler:
            app._default_error_handler_debug(request, response)
            mock_handler.assert_called_once_with(app, request, response)



class TestDefaultErrorHandlerProduction:
    def test_not_found_status(self, app):
        response = _make_response()
        response.status = status.not_found

        with patch("proper.app.fallback_not_found_handler") as mock_handler:
            app._default_error_handler_production(response)
            mock_handler.assert_called_once_with(response)

    def test_gone_status(self, app):
        response = _make_response()
        response.status = status.gone

        with patch("proper.app.fallback_not_found_handler") as mock_handler:
            app._default_error_handler_production(response)
            mock_handler.assert_called_once_with(response)

    def test_forbidden_status(self, app):
        response = _make_response()
        response.status = status.forbidden

        with patch("proper.app.fallback_forbidden_handler") as mock_handler:
            app._default_error_handler_production(response)
            mock_handler.assert_called_once_with(response)

    def test_server_error_status(self, app):
        response = _make_response()
        response.status = status.server_error

        with patch("proper.app.fallback_error_handler") as mock_handler:
            app._default_error_handler_production(response)
            mock_handler.assert_called_once_with(response)



class TestCustomErrorHandler:
    def test_dispatches_to_handler(self, app):
        request = _make_request()
        response = _make_response(app=app)
        request.matched_route = None
        app._custom_error_handler(_ErrorPageController.handle, request, response)
        assert response.body == "custom error page"

    def test_creates_route_if_no_matched_route(self, app):
        request = _make_request()
        response = _make_response(app=app)
        request.matched_route = None
        app._custom_error_handler(_ErrorPageController.handle, request, response)
        assert request.matched_route is not None
        assert isinstance(request.matched_route, Route)

    def test_reuses_existing_matched_route(self, app):
        request = _make_request()
        response = _make_response(app=app)
        original_route = Route(method="GET", path="/original", to=lambda: None)
        request.matched_route = original_route
        app._custom_error_handler(_ErrorPageController.handle, request, response)
        assert request.matched_route is original_route
        assert request.matched_route.to == _ErrorPageController.handle

    def test_clears_matched_params(self, app):
        request = _make_request()
        response = _make_response(app=app)
        request.matched_route = None
        request.matched_params = {"id": "42"}
        app._custom_error_handler(_ErrorPageController.handle, request, response)
        assert request.matched_params == {}



class TestEventDecorators:
    def test_on_error_registers_handler(self, app):
        assert app._on_error == ()

        @app.on_error
        def my_handler():
            pass

        assert my_handler in app._on_error

    def test_on_error_returns_original_function(self, app):
        def my_handler():
            pass

        result = app.on_error(my_handler)
        assert result is my_handler

    def test_on_teardown_registers_handler(self, app):
        assert app._on_teardown == ()

        @app.on_teardown
        def my_handler():
            pass

        assert my_handler in app._on_teardown

    def test_on_teardown_returns_original_function(self, app):
        def my_handler():
            pass

        result = app.on_teardown(my_handler)
        assert result is my_handler

    def test_multiple_on_error_handlers(self, app):
        @app.on_error
        def first():
            pass

        @app.on_error
        def second():
            pass

        assert len(app._on_error) == 2
        assert app._on_error == (first, second)

    def test_multiple_on_teardown_handlers(self, app):
        @app.on_teardown
        def first():
            pass

        @app.on_teardown
        def second():
            pass

        assert len(app._on_teardown) == 2
        assert app._on_teardown == (first, second)



class TestDoRequestErrorFlow:
    def test_controller_exception_returns_500(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        result = client.get("/explode")
        assert result.status == status.server_error

    def test_controller_http_error_preserves_status(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/forbidden", to=_ForbiddenController.index)
        )
        result = client.get("/forbidden")
        assert result.status == status.forbidden

    def test_not_found_error_returns_404(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/missing", to=_NotFoundController.index)
        )
        result = client.get("/missing")
        assert result.status == status.not_found

    def test_unmatched_route_returns_404(self, client):
        result = client.get("/does-not-exist")
        assert result.status == status.not_found

    def test_error_stored_on_response(self, app, client):
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        result = client.get("/explode")
        assert result.status == status.server_error

    def test_on_error_called_on_controller_exception(self, app, client):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        client.get("/explode")
        assert "error" in called

    def test_on_teardown_called_on_controller_exception(self, app, client):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        client.get("/explode")
        assert "teardown" in called

    def test_on_teardown_called_on_success(self, app, client):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/ok", to=_OkController.index)
        )
        client.get("/ok")
        assert "teardown" in called

    def test_on_error_not_called_on_success(self, app, client):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/ok", to=_OkController.index)
        )
        client.get("/ok")
        assert called == []

    def test_custom_error_handler_in_production(self, app, client):
        app.router.add_error_handler(ValueError, _ErrorPageController.handle)
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        result = client.get("/explode")
        assert result.body == "custom error page"

    def test_custom_error_handler_not_used_in_debug(self, app, client):
        app.debug = True
        app.router.add_error_handler(ValueError, _ErrorPageController.handle)
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        result = client.get("/explode")
        assert result.body != "custom error page"

    def test_multiple_on_error_handlers_all_called(self, app, client):
        called = []
        app.on_error(lambda: called.append("first"))
        app.on_error(lambda: called.append("second"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        client.get("/explode")
        assert called == ["first", "second"]

    def test_dbs_close_always_called_on_error(self, app, client):
        mock_db = MagicMock()
        mock_db.autoconnect = False
        mock_db.is_closed.return_value = False
        app.db = {"default": mock_db}

        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        client.get("/explode")
        mock_db.close.assert_called()

    def test_dbs_close_on_success(self, app, client):
        mock_db = MagicMock()
        mock_db.autoconnect = False
        mock_db.is_closed.return_value = False
        app.db = {"default": mock_db}

        app.router.add_route(
            Route(method="GET", path="/ok", to=_OkController.index)
        )
        client.get("/ok")
        mock_db.close.assert_called()

    def test_dbs_rollback_on_outer_error(self, app, client):
        """Rollback happens when _run_pipeline itself propagates an error
        to do_request's outer try/except (e.g. an on_error handler raises)."""
        mock_db = MagicMock()
        mock_db.autoconnect = False
        mock_db.is_closed.return_value = False
        app.db = {"default": mock_db}

        def bad_on_error():
            raise RuntimeError("on_error handler blew up")

        app.on_error(bad_on_error)
        app.router.add_route(
            Route(method="GET", path="/explode", to=_ExplodingController.index)
        )
        client.get("/explode")
        mock_db.rollback.assert_called()

    def test_dbs_skip_autoconnect(self, app, client):
        """Databases with autoconnect=True are not managed by the app."""
        mock_db = MagicMock()
        mock_db.autoconnect = True
        app.db = {"default": mock_db}

        app.router.add_route(
            Route(method="GET", path="/ok", to=_OkController.index)
        )
        client.get("/ok")
        mock_db.connect.assert_not_called()
        mock_db.close.assert_not_called()

    def test_dbs_skip_already_closed(self, app, client):
        """Databases already closed are not closed again."""
        mock_db = MagicMock()
        mock_db.autoconnect = False
        mock_db.is_closed.return_value = True
        app.db = {"default": mock_db}

        app.router.add_route(
            Route(method="GET", path="/ok", to=_OkController.index)
        )
        client.get("/ok")
        mock_db.close.assert_not_called()
