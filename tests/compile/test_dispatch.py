import logging

import pytest
from minijx import Catalog, CompileError, ComponentNotFoundError

import proper.compile.dispatch as lowering
from proper import App, Controller, Route, TestClient, errors
from proper.compile import compiled_views_path
from proper.compile.dispatch import (
    DispatchPlan,
    LoweringError,
    callback_applies,
    class_callbacks,
    lower,
    lower_dispatch,
    plan_for,
    resolve_view,
    validate,
    view_prefixes,
)
from proper.controller.template_resolver import formats_for
from proper.helpers import logger


@pytest.fixture(autouse=True)
def fresh_plans():
    lowering.reset()
    yield
    lowering.reset()


class TestCallbackApplies:
    def test_no_options(self):
        assert callback_applies({}, "show") is True

    def test_only(self):
        assert callback_applies({"only": "show"}, "show") is True
        assert callback_applies({"only": ["show", "edit"]}, "edit") is True
        assert callback_applies({"only": "show"}, "index") is False

    def test_exclude(self):
        assert callback_applies({"exclude": "index"}, "index") is False
        assert callback_applies({"exclude": ("index", "new")}, "new") is False
        assert callback_applies({"exclude": "index"}, "show") is True

    def test_none_values(self):
        assert callback_applies({"only": None, "exclude": None}, "show") is True


class TestClassCallbacks:
    def test_order_follows_the_mro(self):
        class Base(Controller):
            before = {"do": "base_before"}
            after = {"do": "base_after"}

        class Child(Base):
            before = [{"do": "child_before"}]
            after = [{"do": "child_after"}]

        before, after = class_callbacks(Child)
        assert [cb["do"] for cb in before] == ["base_before", "child_before"]
        assert [cb["do"] for cb in after] == ["child_after", "base_after"]

    def test_no_callbacks(self):
        class Plain(Controller):
            pass

        assert class_callbacks(Plain) == ([], [])


class TestViewPrefixes:
    def test_walks_the_mro_and_stops_at_controller(self):
        class ApplicationController(Controller):
            __module__ = "myapp.controllers.application_controller"

        class PostsController(ApplicationController):
            __module__ = "myapp.controllers.admin.posts_controller"

        assert view_prefixes(PostsController) == ("admin/posts", "application")

    def test_class_outside_the_hierarchy(self):
        class Loose:
            __module__ = "myapp.controllers.loose_controller"

        assert view_prefixes(Loose) == ("loose",)

    def test_skips_framework_classes(self):
        class Mixin:
            __module__ = "proper.concerns.something"

        class PostsController(Mixin, Controller):
            __module__ = "myapp.controllers.posts_controller"

        assert view_prefixes(PostsController) == ("posts",)


class TestLowerDispatch:
    def test_filters_callbacks_by_action(self):
        class PostsController(Controller):
            __module__ = "myapp.controllers.posts_controller"
            before = [
                {"do": "set_post", "exclude": ["index", "new", "create"]},
                {"do": "set_form", "exclude": ["index", "show", "delete"]},
                {"do": "validate_form", "only": ["create", "update"]},
            ]
            after = {"do": "log_it", "only": "show"}

            def set_post(self):
                pass

            def set_form(self):
                pass

            def validate_form(self):
                pass

            def log_it(self):
                pass

        plan = lower_dispatch(PostsController, "update")
        assert isinstance(plan, DispatchPlan)
        assert plan.cls is PostsController
        assert plan.action == "update"
        assert plan.before == (("set_post", True), ("set_form", True), ("validate_form", True))
        assert plan.after == ()
        assert plan.prefixes == ("posts",)

        plan = lower_dispatch(PostsController, "show")
        assert plan.before == (("set_post", True),)
        assert plan.after == (("log_it", True),)

        plan = lower_dispatch(PostsController, "index")
        assert plan.before == ()

    def test_property_callback_is_not_a_method(self):
        class MyController(Controller):
            before = {"do": "checks"}

            @property
            def checks(self):
                return []

        plan = lower_dispatch(MyController, "index")
        assert plan.before == (("checks", False),)

    def test_missing_callback_is_kept_for_validation(self):
        class MyController(Controller):
            before = {"do": "nope"}

        plan = lower_dispatch(MyController, "index")
        assert plan.before == (("nope", False),)

    def test_log_flag_follows_the_logger_level(self):
        class MyController(Controller):
            pass

        level = logger.level
        try:
            logger.setLevel(logging.DEBUG)
            assert lower_dispatch(MyController, "index").log is True
            logger.setLevel(logging.INFO)
            assert lower_dispatch(MyController, "index").log is False
        finally:
            logger.setLevel(level)


class TestPlanFor:
    def test_memoized_per_class_and_action(self):
        class MyController(Controller):
            pass

        plan = plan_for(MyController, "index")
        assert plan_for(MyController, "index") is plan
        assert plan_for(MyController, "show") is not plan

    def test_reset_forgets(self):
        class MyController(Controller):
            pass

        plan = plan_for(MyController, "index")
        lowering.reset()
        assert plan_for(MyController, "index") is not plan


class TestValidate:
    def test_ok(self):
        class MyController(Controller):
            before = {"do": "check"}

            def check(self):
                pass

        validate(lower_dispatch(MyController, "index"))

    def test_missing_before(self):
        class MyController(Controller):
            before = {"do": "nope"}

        with pytest.raises(LoweringError, match="MyController: `before` callback `nope`"):
            validate(lower_dispatch(MyController, "index"))

    def test_missing_after(self):
        class MyController(Controller):
            after = {"do": "nope"}

        with pytest.raises(LoweringError, match="`after` callback `nope`"):
            validate(lower_dispatch(MyController, "index"))


class TestFormatsFor:
    def test_known_mimes(self):
        assert formats_for(["application/json", "text/html"], "html") == ("json", "html")

    def test_stops_at_wildcard(self):
        assert formats_for(["text/html", "*/*", "application/json"], "html") == ("html",)

    def test_unknown_mimes_are_skipped(self):
        assert formats_for(["x-made/up", "application/json"], "html") == ("json",)

    def test_default_when_nothing_known(self):
        assert formats_for(["x-made/up"], "html") == ("html",)
        assert formats_for([], "json") == ("json",)

    def test_cached_answer_is_the_same(self):
        first = formats_for(["text/html"], "html")
        assert formats_for(["text/html"], "html") == first


def _catalog(tmp_path, *names):
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<p>{name}</p>")
    catalog = Catalog(auto_reload=False)
    catalog.add_folder(tmp_path)
    return catalog


class TestResolveView:
    def test_prefix_beats_format(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/show.jx", "application/show.json.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts", "application"), False)
        assert resolve_view(plan, catalog, ("json",)) == "posts/show.jx"

    def test_format_specific_first(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/show.jx", "posts/show.json.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts",), False)
        assert resolve_view(plan, catalog, ("json", "html")) == "posts/show.json.jx"
        assert resolve_view(plan, catalog, ("html",)) == "posts/show.jx"

    def test_memoized_per_formats(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/show.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts",), False)
        resolve_view(plan, catalog, ("html",))
        assert plan.views == {("html",): "posts/show.jx"}
        # A memoized answer no longer asks the catalog
        catalog.has_component = lambda name: False
        assert resolve_view(plan, catalog, ("html",)) == "posts/show.jx"

    def test_no_cache(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/show.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts",), False)
        resolve_view(plan, catalog, ("html",), cache=False)
        assert plan.views == {}

    def test_bounded(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/show.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts",), False)
        for n in range(lowering.MAX_VIEWS_PER_PLAN + 10):
            resolve_view(plan, catalog, (f"fmt{n}",))
        assert len(plan.views) == lowering.MAX_VIEWS_PER_PLAN

    def test_missing_names_the_controller(self, tmp_path):
        catalog = _catalog(tmp_path, "posts/index.jx")

        class MyController(Controller):
            pass

        plan = DispatchPlan(MyController, "show", (), (), ("posts",), False)
        with pytest.raises(ComponentNotFoundError, match="MyController.show"):
            resolve_view(plan, catalog, ("html",))


# --- Whole app ---
#
# `Route.resolve` looks the controller up by module and qualified name, so
# the controllers of these tests live at module level.

CALLS: list[str] = []


class PostsController(Controller):
    before = [
        {"do": "load", "exclude": "index"},
        {"do": "extra", "only": "index"},
    ]
    after = {"do": "done"}

    @property
    def extra(self):
        return [self.extra_a, self.extra_b]

    def extra_a(self):
        CALLS.append("extra_a")

    def extra_b(self):
        CALLS.append("extra_b")

    def load(self):
        CALLS.append("load")
        self.post = "Post " + self.params["id"]

    def done(self):
        CALLS.append("done")

    def index(self):
        return "index"

    def show(self):
        pass

    def block(self):
        return "blocked"

    def not_found(self):
        return "nope"


class SecretController(PostsController):
    before = {"do": "block", "only": "blocked"}

    # Defined here, not inherited: a route resolves its controller from the
    # qualified name of the method.
    def blocked(self):
        return "never"


class BrokenController(Controller):
    before = {"do": "nope"}

    def index(self):
        return "index"


def _app(tmp_path, debug=False):
    views = tmp_path / "views"
    views.mkdir(exist_ok=True)
    app = App(__name__, {"SECRET_KEYS": ["*" * 50], "DEBUG": debug})
    app.catalog.auto_reload = debug
    app.catalog.add_folder(views)
    return app, views


class TestLowerApp:
    def test_plans_every_routed_action_and_error_handler(self, tmp_path):
        app, _ = _app(tmp_path)
        app.router.add_route(Route("GET", "posts", to=PostsController.index))
        app.router.add_route(Route("GET", "posts/:id", to=PostsController.show))
        app.router.add_route(Route("POST", "posts", to=PostsController.index))
        app.router.add_route(Route("GET", "old", redirect="/posts"))
        app.router.add_error_handler(errors.NotFound, PostsController.not_found)

        plans = lower(app)
        assert [(p.cls, p.action) for p in plans] == [
            (PostsController, "index"),
            (PostsController, "show"),
            (PostsController, "not_found"),
        ]
        assert plans[1].before == (("load", True),)
        assert plans[1].after == (("done", True),)
        assert plans[0].before == (("extra", False),)
        assert plan_for(PostsController, "show") is plans[1]

    def test_invalid_callback_fails(self, tmp_path):
        app, _ = _app(tmp_path)
        app.router.add_route(Route("GET", "broken", to=BrokenController.index))
        with pytest.raises(LoweringError, match="BrokenController: `before` callback `nope`"):
            lower(app)

    def test_app_lower_validates_in_debug_too(self, tmp_path):
        app, _ = _app(tmp_path, debug=True)
        app.router.add_route(Route("GET", "broken", to=BrokenController.index))
        with pytest.raises(LoweringError):
            app.lower()

    def test_app_lower_in_debug_compiles_and_logs_the_errors(self, tmp_path, caplog):
        import logging

        from proper.helpers import logger

        app, views = _app(tmp_path, debug=True)
        (views / "good.jx").write_text("<p>ok</p>")
        (views / "broken.jx").write_text("{% if %}")
        app.catalog.add_folder(views)
        app.router.add_route(Route("GET", "posts", to=PostsController.index))
        with caplog.at_level(logging.ERROR, logger=logger.name):
            app.lower()  # does not raise: the server starts
        assert app.router._table is not None
        assert plan_for(PostsController, "index") is not None
        assert "Some views do not compile" in caplog.text
        assert "broken.jx:1:" in caplog.text
        assert (compiled_views_path(app) / "good.py").is_file()
        assert app.catalog.render("good.jx") == "<p>ok</p>"
        with pytest.raises(CompileError, match="broken.jx:1:"):
            app.catalog.render("broken.jx")

    def test_app_lower_compiles_the_views(self, tmp_path):
        app, views = _app(tmp_path)
        (views / "page.jx").write_text("<p>hi</p>")
        app.catalog.add_folder(views)
        app.lower()
        assert (compiled_views_path(app) / "page.py").is_file()
        assert app.catalog.render("page.jx") == "<p>hi</p>"

    def test_app_lower_surfaces_a_broken_view(self, tmp_path):
        app, views = _app(tmp_path)
        (views / "broken.jx").write_text("{% if %}")
        app.catalog.add_folder(views)
        with pytest.raises(CompileError, match="broken.jx:1:"):
            app.lower()

    def test_app_lower_validates(self, tmp_path):
        app, _ = _app(tmp_path)
        app.router.add_route(Route("GET", "broken", to=BrokenController.index))
        with pytest.raises(LoweringError):
            app.lower()


class TestServing:
    """The same requests through the lowered dispatch and through a debug app,
    where nothing is memoized, must answer the same."""

    def _make(self, tmp_path, debug):
        app, views = _app(tmp_path, debug=debug)
        (views / "test_dispatch").mkdir()
        (views / "test_dispatch" / "show.jx").write_text("{#def post #}<h1>{{ post }}</h1>")
        (views / "test_dispatch" / "show.json.jx").write_text('{#def post #}{"post": "{{ post }}"}')
        app.catalog.add_folder(views)
        app.router.add_route(Route("GET", "posts", to=PostsController.index))
        app.router.add_route(Route("GET", "posts/:id", to=PostsController.show))
        app.router.add_route(Route("GET", "secret/:id", to=SecretController.blocked))
        app.lower()
        CALLS.clear()
        return TestClient(app)

    @pytest.mark.parametrize("debug", [False, True])
    def test_callbacks_and_views(self, tmp_path, debug):
        client = self._make(tmp_path, debug)

        resp = client.get("/posts")
        assert resp.body == "index"
        assert CALLS == ["extra_a", "extra_b", "done"]

        CALLS.clear()
        resp = client.get("/posts/7")
        assert resp.body == "<h1>Post 7</h1>"
        assert CALLS == ["load", "done"]

        resp = client.get("/posts/7", headers={"accept": "application/json"})
        assert resp.body == '{"post": "Post 7"}'

        # Same answer the second time, now from the memo (or not, in debug)
        resp = client.get("/posts/7", headers={"accept": "application/json"})
        assert resp.body == '{"post": "Post 7"}'
        plan = plan_for(PostsController, "show")
        assert bool(plan.views) is (not debug)

        CALLS.clear()
        resp = client.get("/secret/1")
        assert resp.body == "blocked"
        assert CALLS == ["load"]
