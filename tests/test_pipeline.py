"""Tests for the App.__call__ / run_pipeline flow and individual middleware."""

from unittest.mock import patch

import pytest

from proper import App, current, status
from proper.constants import FLASHES_SESSION_KEY
from proper.controller import Controller
from proper.helpers import DotDict
from proper.middleware import (
    copy_session,
    head_to_get,
    match,
    method_override,
    redirect,
    strip_body_if_head,
    update_session_cookie,
)
from proper.middleware.dispatch import dispatch
from proper.middleware.match import LOCAL_HOSTS
from proper.request import Request
from proper.response import Response
from proper.router import Route


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    return App("tests", config)


@pytest.fixture()
def make_co(app):
    def _make_co(**request_kw):
        request = Request(**request_kw)
        response = Response(app=app)
        return Controller(app, request, response)
    return _make_co


@pytest.fixture()
def co(make_co):
    return make_co()


# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS — individual middleware functions
# ═══════════════════════════════════════════════════════════════════


# ── head_to_get / strip_body_if_head ────────────────────────────────


class TestHeadToGet:
    def test_rewrites_head_to_get(self, make_co):
        co = make_co(REQUEST_METHOD="HEAD")
        head_to_get(None, co.request, None)
        assert co.request.method == "GET"

    def test_preserves_original_request_method(self, make_co):
        co = make_co(REQUEST_METHOD="HEAD")
        head_to_get(None, co.request, None)
        assert co.request.request_method == "HEAD"

    def test_does_not_touch_get(self, co):
        head_to_get(None, co.request, None)
        assert co.request.method == "GET"

    def test_does_not_touch_post(self, make_co):
        co = make_co(REQUEST_METHOD="POST")
        head_to_get(None, co.request, None)
        assert co.request.method == "POST"


class TestStripBodyIfHead:
    def test_strips_body_when_original_was_head(self, make_co):
        co = make_co(REQUEST_METHOD="HEAD")
        co.response.body = "hello"
        strip_body_if_head(None, co.request, co.response)
        assert co.response.body == ""

    def test_keeps_body_for_get(self, co):
        co.response.body = "hello"
        strip_body_if_head(None, co.request, co.response)
        assert co.response.body == "hello"


# ── method_override ─────────────────────────────────────────────────


class TestMethodOverride:
    def test_override_via_header(self, make_co):
        co = make_co(REQUEST_METHOD="POST", HTTP_X_HTTP_METHOD_OVERRIDE="PUT")
        method_override(None, co.request, None)
        assert co.request.method == "PUT"

    def test_override_via_query_param(self, make_co):
        co = make_co(REQUEST_METHOD="POST", QUERY_STRING="_method=DELETE")
        method_override(None, co.request, None)
        assert co.request.method == "DELETE"

    def test_override_via_form_body(self, make_co):
        co = make_co(
            REQUEST_METHOD="POST",
            CONTENT_TYPE="application/x-www-form-urlencoded",
        )
        co.request._form = DotDict({"_method": "PATCH"})
        method_override(None, co.request, None)
        assert co.request.method == "PATCH"

    def test_ignores_non_post(self, make_co):
        co = make_co(REQUEST_METHOD="GET", HTTP_X_HTTP_METHOD_OVERRIDE="PUT")
        method_override(None, co.request, None)
        assert co.request.method == "GET"

    def test_ignores_invalid_override(self, make_co):
        co = make_co(REQUEST_METHOD="POST", HTTP_X_HTTP_METHOD_OVERRIDE="GET")
        method_override(None, co.request, None)
        assert co.request.method == "POST"

    def test_override_to_query(self, make_co):
        co = make_co(REQUEST_METHOD="POST", HTTP_X_HTTP_METHOD_OVERRIDE="QUERY")
        method_override(None, co.request, None)
        assert co.request.method == "QUERY"

    def test_case_insensitive_override(self, make_co):
        co = make_co(REQUEST_METHOD="POST", HTTP_X_HTTP_METHOD_OVERRIDE="put")
        method_override(None, co.request, None)
        assert co.request.method == "PUT"


# ── match ───────────────────────────────────────────────────────────


class TestMatch:
    def test_sets_matched_route_and_params(self, app, make_co):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(Route(method="GET", path="/items/:id", to=Dummy.index))
        co = make_co(REQUEST_METHOD="GET", PATH_INFO="/items/42", HTTP_HOST="example.com")
        match(app, co.request, co.response)
        assert co.request.matched_route is not None
        assert co.request.matched_params["id"] == "42"

    def test_raises_on_no_match(self, app, make_co):
        from proper.errors import MatchNotFound

        co = make_co(REQUEST_METHOD="GET", PATH_INFO="/nope", HTTP_HOST="example.com")
        with pytest.raises(MatchNotFound):
            match(app, co.request, None)

    @pytest.mark.parametrize("host", LOCAL_HOSTS)
    def test_local_host_treated_as_none(self, app, make_co, host):
        class Dummy(Controller):
            def index(self):
                pass

        app.router.add_route(Route(method="GET", path="/ok", to=Dummy.index))
        co = make_co(REQUEST_METHOD="GET", PATH_INFO="/ok", HTTP_HOST=host)
        match(app, co.request, None)
        assert co.request.matched_route is not None


# ── redirect ────────────────────────────────────────────────────────


class TestRedirect:
    def test_returns_none_when_no_route(self, co):
        co.request.matched_route = None
        assert redirect(None, co.request, co.response) is None

    def test_returns_none_when_route_is_not_redirect(self, co):
        co.request.matched_route = Route(method="GET", path="/", to=lambda: None)
        assert redirect(None, co.request, co.response) is None

    def test_returns_response_when_redirect(self, co):
        route = Route(method="GET", path="/old", redirect="/new")
        co.request.matched_route = route
        co.request.matched_params = {}
        result = redirect(None, co.request, co.response)
        assert result is co.response
        assert co.response.status == status.temporary_redirect

    def test_redirect_interpolates_params(self, co):
        route = Route(method="GET", path="/old/:id", redirect="/new/{id}")
        co.request.matched_route = route
        co.request.matched_params = {"id": "42"}
        redirect(None, co.request, co.response)
        location = co.response.headers.get("Location")
        assert location == "/new/42"


# ── session middleware ──────────────────────────────────────────────


class TestCopySession:
    def test_copies_session_from_cookie(self, app, make_co):
        co = make_co(REQUEST_METHOD="GET", app=app)
        copy_session(app, co.request, co.response)
        assert co.request.session == {}
        assert co.response.session == {}

    def test_strips_flashes_from_response_session(self, app, make_co):
        session_data = DotDict({
            "user": "alice",
            FLASHES_SESSION_KEY: [("info", "saved!")],
        })
        with patch(
            "proper.middleware.session._find_session_by_cookie",
            return_value=session_data,
        ):
            co = make_co(REQUEST_METHOD="GET")
            copy_session(app, co.request, co.response)

        assert FLASHES_SESSION_KEY in co.request.session
        assert co.request.session[FLASHES_SESSION_KEY] == [("info", "saved!")]

        assert FLASHES_SESSION_KEY not in co.response.session
        assert co.response.session["user"] == "alice"

    def test_skips_for_head(self, app, make_co):
        co = make_co(REQUEST_METHOD="HEAD")
        copy_session(app, co.request, co.response)
        assert not hasattr(co.request, "session") or co.request.session == DotDict()

    def test_skips_for_options(self, app, make_co):
        co = make_co(REQUEST_METHOD="OPTIONS")
        copy_session(app, co.request, co.response)
        assert not hasattr(co.request, "session") or co.request.session == DotDict()


class TestUpdateSessionCookie:
    def test_no_cookie_when_session_unchanged(self, app, co):
        co.request.session = DotDict({"foo": "bar"})
        co.response.session = DotDict({"foo": "bar"})
        update_session_cookie(app, co.request, co.response)
        cookies = co.response._get_cookie_tuples()
        session_cookies = [c for c in cookies if "_session" in c[1]]
        assert session_cookies == []

    def test_sets_cookie_when_session_modified(self, app, co):
        current.app = app
        co.request.session = DotDict({})
        co.response.session = DotDict({"foo": "bar"})
        update_session_cookie(app, co.request, co.response)
        cookies = co.response._get_cookie_tuples()
        session_cookies = [c for c in cookies if "_session" in c[1]]
        assert len(session_cookies) == 1

    def test_unsets_cookie_when_session_cleared(self, app, co):
        co.request.session = DotDict({"foo": "bar"})
        co.response.session = DotDict()
        update_session_cookie(app, co.request, co.response)
        cookies = co.response._get_cookie_tuples()
        session_cookies = [c for c in cookies if "_session" in c[1]]
        assert len(session_cookies) == 1
        cookie_val = session_cookies[0][1]
        assert "max-age=0" in cookie_val.lower() or "expires=" in cookie_val.lower()

    def test_skips_for_head(self, app, make_co):
        co = make_co(REQUEST_METHOD="HEAD")
        co.request.session = DotDict({})
        co.response.session = DotDict({"changed": True})
        update_session_cookie(app, co.request, co.response)
        cookies = co.response._get_cookie_tuples()
        session_cookies = [c for c in cookies if "_session" in c[1]]
        assert session_cookies == []


# ── dispatch ────────────────────────────────────────────────────────


class _DispatchHello(Controller):
    def index(self):
        return "hello"

    def show(self):
        return "page"


class TestDispatch:
    def test_dispatches_to_controller_action(self, app, co):
        route = Route(method="GET", path="/hello", to=_DispatchHello.index)
        co.request.matched_route = route
        co.request.matched_params = {}
        dispatch(app, co.request, co.response)
        assert co.response.body == "hello"

    def test_sets_matched_action(self, app, co):
        route = Route(method="GET", path="/page", to=_DispatchHello.show)
        co.request.matched_route = route
        co.request.matched_params = {}
        dispatch(app, co.request, co.response)
        assert co.request.matched_action == "show"


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS — full pipeline via AppTest helpers
# ═══════════════════════════════════════════════════════════════════


class GreetController(Controller):
    def index(self):
        return "hello"

    def show(self):
        name = self.params.get("name", "world")
        return f"hello {name}"

    def create(self):
        return "created"

    def update(self):
        return f"updated via {self.request.method}"

    def explode(self):
        raise ValueError("boom")


class SessionController(Controller):
    def write_session(self):
        self.response.session["color"] = "blue"
        return "ok"

    def read_session(self):
        return self.response.session.get("color", "none")


class TestPipelineGet:
    def test_happy_path(self, app):
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = app.get("/hello")
        assert result.status == status.ok
        assert result.body == "hello"

    def test_with_path_params(self, app):
        app.router.add_route(
            Route(method="GET", path="/hello/:name", to=GreetController.show)
        )
        result = app.get("/hello/alice")
        assert result.status == status.ok
        assert result.body == "hello alice"


class TestPipelineHead:
    def test_head_returns_empty_body(self, app):
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        result = app.head("/hello")
        assert result.status == status.ok
        assert result.body == ""


class TestPipelineMethodOverride:
    def test_post_overridden_to_put(self, app):
        app.router.add_route(
            Route(method="PUT", path="/items", to=GreetController.update)
        )
        result = app.post("/items?_method=PUT")
        assert result.status == status.ok
        assert result.body == "updated via PUT"

    def test_post_overridden_via_header(self, app):
        app.router.add_route(
            Route(method="PATCH", path="/items", to=GreetController.update)
        )
        result = app.post(
            "/items",
            headers={"HTTP_X_HTTP_METHOD_OVERRIDE": "PATCH"},
        )
        assert result.status == status.ok
        assert result.body == "updated via PATCH"


class TestPipelineNotFound:
    def test_404_for_unmatched_route(self, app):
        result = app.get("/nonexistent")
        assert result.status == status.not_found


class TestPipelineRedirect:
    def test_redirect_route(self, app):
        app.router.add_route(
            Route(method="GET", path="/old", redirect="/new")
        )
        result = app.get("/old")
        assert "307" in result.status
        assert result.headers.get("Location") == "/new"

    def test_redirect_with_params(self, app):
        app.router.add_route(
            Route(method="GET", path="/old/:id", redirect="/new/{id}")
        )
        result = app.get("/old/99")
        assert "307" in result.status
        assert result.headers.get("Location") == "/new/99"


class TestPipelineHooks:
    def test_on_teardown_always_runs(self, app):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        app.get("/hello")
        assert called == ["teardown"]

    def test_on_teardown_runs_on_error(self, app):
        called = []
        app.on_teardown(lambda: called.append("teardown"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        app.get("/explode")
        assert "teardown" in called

    def test_on_error_runs_on_exception(self, app):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/explode", to=GreetController.explode)
        )
        app.get("/explode")
        assert "error" in called

    def test_on_error_not_called_on_success(self, app):
        called = []
        app.on_error(lambda: called.append("error"))
        app.router.add_route(
            Route(method="GET", path="/hello", to=GreetController.index)
        )
        app.get("/hello")
        assert called == []


class TestPipelineEarlyReturn:
    def test_redirect_stops_pipeline(self, app):
        """A redirect route should never reach dispatch."""
        app.router.add_route(
            Route(method="GET", path="/redir", redirect="/target")
        )
        result = app.get("/redir")
        assert "307" in result.status
        # Body is the redirect HTML, not a controller response
        assert "hello" not in (result.body or "")
