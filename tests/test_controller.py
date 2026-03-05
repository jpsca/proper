"""Tests for proper.controller — Controller and StaticFilesController."""

from unittest.mock import MagicMock

import pytest

from proper.controller import RX_FINGERPRINT, Controller, StaticFilesController
from proper.errors import NotFound
from proper.helpers import DotDict, MultiDict
from proper.request import Request, make_test_scope
from proper.response import Response
from proper.status import not_modified


# ── helpers ──────────────────────────────────────────────────────────


def _make_controller(cls=Controller, **request_kw):
    app = MagicMock()
    app.config = DotDict({
        "MAX_QUERY_SIZE": 1_048_576,
        "MAX_CONTENT_LENGTH": 8_388_608,
    })
    scope = make_test_scope(**request_kw)
    scope["app"] = app
    request = Request(scope)
    response = Response(scope)
    return cls(request, response)


# ── Controller basics ────────────────────────────────────────────────


class TestControllerInit:
    def test_stores_app_request_response(self):
        app = MagicMock()
        scope = make_test_scope()
        scope["app"] = app
        request = Request(scope)
        response = Response(scope)
        co = Controller(request, response)
        assert co.app is app
        assert co.request is request
        assert co.response is response

    def test_default_etag(self):
        assert Controller.etag == ""


# ── params ───────────────────────────────────────────────────────────


class TestParams:
    def test_merges_query_form_and_matched_params(self):
        co = _make_controller(url="/?a=1")
        co.request.form = MultiDict([("b", "2")])
        co.request.matched_params = {"c": "3"}
        params = co.params
        assert params.get("a") == "1"
        assert params.get("b") == "2"
        assert params.get("c") == "3"

    def test_matched_params_none(self):
        co = _make_controller()
        co.request.matched_params = None
        params = co.params
        assert isinstance(params, MultiDict)

    def test_returns_new_multidict_each_time(self):
        co = _make_controller()
        assert co.params is not co.params


# ── defaults ─────────────────────────────────────────────────────────


class TestDefaults:
    def test_from_matched_route(self):
        co = _make_controller()
        route = MagicMock()
        route.defaults = {"root": "/static", "public": True}
        co.request.matched_route = route
        assert co.defaults == {"root": "/static", "public": True}

    def test_no_matched_route(self):
        co = _make_controller()
        co.request.matched_route = None
        assert co.defaults == {}


# ── render ───────────────────────────────────────────────────────────


class TestRender:
    def test_render_json(self):
        co = _make_controller()
        result = co.render(json={"key": "value"})
        assert '"key"' in result
        assert '"value"' in result
        assert co.response.mimetype == "application/json"

    def test_render_text(self):
        co = _make_controller()
        result = co.render(text="hello world")
        assert result == "hello world"
        assert co.response.mimetype == "text/plain"

    def test_render_with_status(self):
        co = _make_controller()
        co.render(text="ok", status=201)
        assert co.response.status == 201

    def test_render_template(self):
        co = _make_controller()
        co.app.catalog.render.return_value = "<html>rendered</html>"
        result = co.render("my_template.jinja")
        co.app.catalog.render.assert_called_once()
        assert result == "<html>rendered</html>"

    def test_render_json_takes_priority_over_text(self):
        co = _make_controller()
        co.render(json={"a": 1}, text="ignored")
        assert co.response.mimetype == "application/json"


# ── _should_run_callback ─────────────────────────────────────────────


class TestShouldRunCallback:
    def test_empty_options(self):
        co = _make_controller()
        assert co._should_run_callback({}) is True

    def test_only_matches(self):
        co = _make_controller()
        co.request.matched_action = "show"
        assert co._should_run_callback({"only": "show"}) is True

    def test_only_no_match(self):
        co = _make_controller()
        co.request.matched_action = "index"
        assert co._should_run_callback({"only": "show"}) is False

    def test_only_list(self):
        co = _make_controller()
        co.request.matched_action = "edit"
        assert co._should_run_callback({"only": ["show", "edit"]}) is True

    def test_exclude_matches(self):
        co = _make_controller()
        co.request.matched_action = "destroy"
        assert co._should_run_callback({"exclude": "destroy"}) is False

    def test_exclude_no_match(self):
        co = _make_controller()
        co.request.matched_action = "show"
        assert co._should_run_callback({"exclude": "destroy"}) is True

    def test_exclude_list(self):
        co = _make_controller()
        co.request.matched_action = "edit"
        assert co._should_run_callback({"exclude": ["edit", "destroy"]}) is False

    def test_only_none_exclude_none(self):
        co = _make_controller()
        co.request.matched_action = "show"
        assert co._should_run_callback({"only": None, "exclude": None}) is True


# ── _call ────────────────────────────────────────────────────────────


class TestCall:
    def test_return_value_sets_body(self):
        class MyController(Controller):
            def index(self):
                return "Hello"

        co = _make_controller(cls=MyController)
        co._call("index")
        assert co.response.body == "Hello"

    def test_fresh_response_sets_not_modified(self):
        class MyController(Controller):
            def index(self):
                self.response.set_etag(123)
                return "Hello"

        etag = 'W/"40bd001563085fc35165329ea1ff5c5ecbdbbeef"'
        co = _make_controller(cls=MyController, headers=[("if-none-match", etag)])
        co._call("index")
        assert co.response.status == not_modified
        assert co.response.body == ""

    def test_no_return_infers_template(self):
        class MyController(Controller):
            def show(self):
                pass

        co = _make_controller(cls=MyController)
        co.app.catalog.render.return_value = "<html/>"
        co._call("show")
        assert co.response.body == "<html/>"
        # Check the inferred template name
        call_args = co.app.catalog.render.call_args
        template_name = call_args[0][0]
        assert template_name.endswith("/show.jinja")

    def test_no_return_body_already_set(self):
        class MyController(Controller):
            def index(self):
                self.response.body = "already set"

        co = _make_controller(cls=MyController)
        co._call("index")
        assert co.response.body == "already set"

    def test_inferred_view_strips_controller_suffix(self):
        class MyController(Controller):
            __module__ = "myapp.pages.users_controller"

            def edit(self):
                pass

        co = _make_controller(cls=MyController)
        co.app.catalog.render.return_value = ""
        co._call("edit")
        template = co.app.catalog.render.call_args[0][0]
        # "myapp.pages.users_controller".split(".", 2) -> ["myapp", "pages", "users_controller"]
        # take [-1] -> "users_controller", removesuffix -> "users", replace "." -> "users"
        assert template == "pages/users/edit.jinja"

    def test_inferred_view_module_path(self):
        # split(".", 2) on "myapp.web.admin.dashboard" -> ["myapp", "web", "admin.dashboard"]
        # [-1] -> "admin.dashboard", replace "." -> "admin/dashboard"
        class MyController(Controller):
            __module__ = "myapp.web.admin.dashboard"

            def index(self):
                pass

        co = _make_controller(cls=MyController)
        co.app.catalog.render.return_value = ""
        co._call("index")
        template = co.app.catalog.render.call_args[0][0]
        assert template == "pages/admin/dashboard/index.jinja"


# ── _dispatch ────────────────────────────────────────────────────────


class TestDispatch:
    def test_simple_dispatch(self):
        class MyController(Controller):
            def index(self):
                return "dispatched"

        co = _make_controller(cls=MyController)
        co._dispatch("index")
        assert co.response.body == "dispatched"

    def test_before_callback(self):
        called = []

        class MyController(Controller):
            before = {"do": "check_auth", "only": "index"}

            def check_auth(self):
                called.append("before")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["before", "index"]

    def test_before_callback_skipped_by_only(self):
        called = []

        class MyController(Controller):
            before = {"do": "check_auth", "only": "create"}

            def check_auth(self):
                called.append("before")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["index"]

    def test_before_sets_body_stops_dispatch(self):
        called = []

        class MyController(Controller):
            before = {"do": "block"}

            def block(self):
                self.response.body = "blocked"

            def index(self):
                called.append("index")
                return "should not reach"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert co.response.body == "blocked"
        assert called == []

    def test_after_callback(self):
        called = []

        class MyController(Controller):
            after = {"do": "log_it"}

            def log_it(self):
                called.append("after")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["index", "after"]

    def test_after_callback_skipped_by_exclude(self):
        called = []

        class MyController(Controller):
            after = {"do": "log_it", "exclude": "index"}

            def log_it(self):
                called.append("after")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["index"]

    def test_before_callback_skipped_by_exclude_tuple(self):
        called = []

        class MyController(Controller):
            before = {"do": "set_post", "exclude": ("index", "new", "create")}

            def set_post(self):
                called.append("before")

            def index(self):
                called.append("index")
                return "ok"

            def show(self):
                called.append("show")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["index"]

        called.clear()
        co = _make_controller(cls=MyController)
        co.request.matched_action = "show"
        co._dispatch("show")
        assert called == ["before", "show"]

    def test_before_callback_skipped_by_exclude_list(self):
        called = []

        class MyController(Controller):
            before = {"do": "set_post", "exclude": ["index", "new", "create"]}

            def set_post(self):
                called.append("before")

            def index(self):
                called.append("index")
                return "ok"

            def show(self):
                called.append("show")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["index"]

        called.clear()
        co = _make_controller(cls=MyController)
        co.request.matched_action = "show"
        co._dispatch("show")
        assert called == ["before", "show"]

    def test_before_and_after_with_inheritance(self):
        called = []

        class BaseController(Controller):
            before = {"do": "base_before"}

            def base_before(self):
                called.append("base_before")

        class ChildController(BaseController):
            after = {"do": "child_after"}

            def child_after(self):
                called.append("child_after")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=ChildController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert "base_before" in called
        assert "index" in called
        assert "child_after" in called

    def test_before_with_list_of_callbacks(self):
        called = []

        class MyController(Controller):
            before = {"do": "checks"}

            @property
            def checks(self):
                return [self.check_a, self.check_b]

            def check_a(self):
                called.append("a")

            def check_b(self):
                called.append("b")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert called == ["a", "b", "index"]

    def test_before_as_list_of_dicts(self):
        called = []

        class MyController(Controller):
            before = [
                {"do": "load_resource"},
                {"do": "check_access", "only": "edit"},
            ]

            def load_resource(self):
                called.append("load")

            def check_access(self):
                called.append("access")

            def edit(self):
                called.append("edit")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "edit"
        co._dispatch("edit")
        assert called == ["load", "access", "edit"]

    def test_before_list_only_filter(self):
        called = []

        class MyController(Controller):
            before = [
                {"do": "load_resource"},
                {"do": "check_access", "only": "edit"},
            ]

            def load_resource(self):
                called.append("load")

            def check_access(self):
                called.append("access")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        # check_access should be skipped for "index"
        assert called == ["load", "index"]

    def test_after_as_list_of_dicts(self):
        called = []

        class MyController(Controller):
            after = [
                {"do": "log_action"},
                {"do": "notify", "only": "create"},
            ]

            def log_action(self):
                called.append("log")

            def notify(self):
                called.append("notify")

            def create(self):
                called.append("create")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "create"
        co._dispatch("create")
        assert called == ["create", "log", "notify"]

    def test_before_list_early_return_stops_all(self):
        called = []

        class MyController(Controller):
            before = [
                {"do": "block"},
                {"do": "second"},
            ]

            def block(self):
                self.response.body = "blocked"

            def second(self):
                called.append("second")

            def index(self):
                called.append("index")
                return "ok"

        co = _make_controller(cls=MyController)
        co.request.matched_action = "index"
        co._dispatch("index")
        assert co.response.body == "blocked"
        assert called == []


# ── RX_FINGERPRINT ───────────────────────────────────────────────────


class TestRxFingerprint:
    def test_matches_fingerprinted_name(self):
        fingerprint = "a" * 64
        m = RX_FINGERPRINT.match(f"app-{fingerprint}")
        assert m is not None
        assert m.group(1) == "app"
        assert m.group(2) == fingerprint

    def test_no_match_without_fingerprint(self):
        assert RX_FINGERPRINT.match("app") is None

    def test_no_match_short_hash(self):
        assert RX_FINGERPRINT.match("app-abc123") is None

    def test_match_with_dots_in_stem(self):
        fingerprint = "b" * 64
        m = RX_FINGERPRINT.match(f"app.min-{fingerprint}")
        assert m is not None
        assert m.group(1) == "app.min"


# ── StaticFilesController ────────────────────────────────────────────


class TestStaticFilesController:
    def _make(self, tmp_path, filename="hello.txt", content="Hello",
              file_param=None, public=True, allowed_ext=None,
              if_modified_since=None, x_sendfile=""):
        filepath = tmp_path / filename
        filepath.write_text(content)

        request_kw = {}
        if if_modified_since:
            request_kw["headers"] = [("if-modified-since", if_modified_since)]

        co = _make_controller(cls=StaticFilesController, **request_kw)

        route = MagicMock()
        defaults = DotDict({"root": str(tmp_path), "public": public})
        if allowed_ext is not None:
            defaults["allowed_ext"] = allowed_ext
        route.defaults = defaults
        co.request.matched_route = route

        query = MultiDict([("file", file_param or filename)])
        co.request._query = query

        co.app.config = DotDict({"STATIC_X_SENDFILE_HEADER": x_sendfile})

        return co, filepath

    def test_serves_file(self, tmp_path):
        co, filepath = self._make(tmp_path)
        co.show()
        assert co.response.body is not None
        assert "hello.txt" in co.response.headers.get("content-disposition")

    def test_file_not_found(self, tmp_path):
        co, _ = self._make(tmp_path, file_param="nonexistent.txt")
        with pytest.raises(NotFound, match="does not exists"):
            co.show()

    def test_allowed_ext_blocks(self, tmp_path):
        co, _ = self._make(tmp_path, filename="data.exe", allowed_ext=[".txt", ".css"])
        with pytest.raises(NotFound, match="does not exists"):
            co.show()

    def test_allowed_ext_passes(self, tmp_path):
        co, _ = self._make(tmp_path, filename="style.css", allowed_ext=[".css", ".js"])
        co.show()
        assert co.response.body is not None

    def test_fingerprinted_file(self, tmp_path):
        fingerprint = "a" * 64
        # The actual file without fingerprint
        (tmp_path / "app.js").write_text("js content")

        co, _ = self._make(tmp_path, file_param=f"app-{fingerprint}.js")
        co.show()
        # Should have immutable cache control
        assert co.response.cache_control == [
            "max-age=31536000", "public", "immutable",
        ]

    def test_non_fingerprinted_cache_control(self, tmp_path):
        co, _ = self._make(tmp_path)
        co.show()
        assert co.response.cache_control == [
            "max-age=0", "public", "must-revalidate",
        ]

    def test_private_cache_control(self, tmp_path):
        co, _ = self._make(tmp_path, public=False)
        co.show()
        assert "private" in co.response.cache_control

    def test_cors_header_set(self, tmp_path):
        co, _ = self._make(tmp_path)
        co.show()
        assert co.response.headers.get("Access-Control-Allow-Origin") == "*"

    def test_not_modified_when_fresh(self, tmp_path):
        co, filepath = self._make(
            tmp_path,
            if_modified_since="Thu, 01 Jan 2099 00:00:00 GMT",
        )
        co.show()
        assert co.response.status == not_modified

    def test_sets_last_modified(self, tmp_path):
        co, filepath = self._make(tmp_path)
        co.show()
        assert co.response.last_modified is not None

    def test_leading_slash_stripped_from_file(self, tmp_path):
        co, _ = self._make(tmp_path, file_param="/hello.txt")
        co.show()
        assert co.response.body is not None
