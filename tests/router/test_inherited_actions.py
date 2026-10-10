"""Routes to an action that a controller inherits from a parent controller.

`resource()` routes it on the decorated class: the route's name, the
instance that runs the action, its callbacks and its views are those of that
class. A route made from a method object (`get()(...)`, `Route(to=...)`)
belongs to the class that defines the method, because the function is the
same object in the parent and in the subclass.

`Route.resolve` imports the class that defines a method by module and
qualified name, so these controllers live at module level.
"""

import pytest

import proper.compile.dispatch as lowering
from proper import App, Controller, Route, TestClient
from proper.errors import ConfigError


CALLS: list[str] = []


class ApplicationController(Controller):
    __module__ = "myapp.controllers.application_controller"

    before = {"do": "app_before"}
    after = {"do": "app_after"}

    def app_before(self):
        CALLS.append(f"app_before {type(self).__name__}")

    def app_after(self):
        CALLS.append(f"app_after {type(self).__name__}")

    def index(self):
        CALLS.append(f"index {type(self).__name__}")
        return f"index on {type(self).__name__}"

    def show(self):
        CALLS.append(f"show {type(self).__name__}")


class ArticleController(ApplicationController):
    __module__ = "myapp.controllers.article_controller"

    before = {"do": "article_before"}
    after = {"do": "article_after"}

    def article_before(self):
        CALLS.append("article_before")

    def article_after(self):
        CALLS.append("article_after")

    def edit(self):
        return f"edit on {type(self).__name__}"


@pytest.fixture(autouse=True)
def fresh():
    lowering.reset()
    CALLS.clear()
    yield
    lowering.reset()


def make_app(tmp_path):
    views = tmp_path / "views"
    for folder in ("article", "application"):
        (views / folder).mkdir(parents=True)
    (views / "application" / "show.jx").write_text("application/show")
    (views / "article" / "show.jx").write_text("article/show")
    app = App(__name__, {"SECRET_KEYS": ["*" * 50]})
    app.catalog.add_folder(views)
    return app


def test_resource_routes_an_inherited_action_on_the_decorated_class(tmp_path):
    app = make_app(tmp_path)
    app.router.resource("articles")(ArticleController)
    routes = {route.name: route for route in app.routes}
    assert set(routes) == {"Article.index", "Article.show", "Article.edit"}
    for route in routes.values():
        assert route.controller is ArticleController
        assert route.resolve()[0] is ArticleController
    assert routes["Article.index"].resolve() == (ArticleController, "index")

    client = TestClient(app)
    resp = client.get("/articles")
    # Before, it ran on an ApplicationController, without the callbacks of
    # ArticleController.
    assert resp.body == "index on ArticleController"
    assert CALLS == [
        "app_before ArticleController",
        "article_before",
        "index ArticleController",
        "article_after",
        "app_after ArticleController",
    ]

    # The view of the decorated class comes first.
    resp = client.get("/articles/3")
    assert resp.body == "article/show"

    assert client.get("/articles/3/edit").body == "edit on ArticleController"


def test_resource_controller_prefix_is_the_decorated_class(tmp_path):
    app = make_app(tmp_path)
    app.router.resource("articles")(ArticleController)

    class Obj:
        article_id = 7

    class OnlyId:
        id = 5

    for name in ("Article.show", "Article.edit"):
        route = app.router._routes_by_name[name]
        assert route.controller_prefix == "article_"
    # `show` is inherited: its `:article_id` is read from `id` too, as for
    # the class's own `edit`.
    assert app.url_for("Article.show", Obj()) == "/articles/7"
    assert app.url_for("Article.show", OnlyId()) == "/articles/5"
    assert app.url_for("Article.edit", OnlyId()) == "/articles/5/edit"
    assert app.url_for("Article.index") == "/articles"


def test_a_route_from_an_inherited_method_object_keeps_the_defining_class(tmp_path):
    # `ArticleController.index` is `ApplicationController.index`: nothing in
    # it tells which class it was read from.
    assert ArticleController.index is ApplicationController.index
    app = make_app(tmp_path)
    app.router.get("feed")(ArticleController.index)
    app.router.add_route(Route("GET", "feed2", to=ArticleController.show))
    feed, feed2 = app.routes
    assert feed.name == "Application.index"
    assert feed2.name == "Application.show"
    assert feed.controller is None
    assert feed.controller_prefix == "application_"
    assert feed.resolve() == (ApplicationController, "index")

    client = TestClient(app)
    assert client.get("/feed").body == "index on ApplicationController"
    assert CALLS == [
        "app_before ApplicationController",
        "index ApplicationController",
        "app_after ApplicationController",
    ]
    assert app.url_for("Application.index") == "/feed"


def test_route_controller_argument():
    route = Route(
        "GET", "/a", to=ApplicationController.index, controller=ArticleController
    )
    assert route.name == "Application.index"
    assert route.controller is ArticleController
    assert route.controller_prefix == "article_"
    assert route.resolve() == (ArticleController, "index")
    assert route != Route("GET", "/a", to=ApplicationController.index)
    assert route == Route(
        "GET", "/a", to=ApplicationController.index, controller=ArticleController
    )


class OverridingController(ApplicationController):
    __module__ = "myapp.controllers.overriding_controller"

    def index(self):
        return "override"


def test_route_controller_must_have_to_as_its_action():
    # The request would run `OverridingController.index`, not `to`.
    with pytest.raises(ConfigError, match="not the `index` action of"):
        Route(
            "GET", "/a", to=ApplicationController.index, controller=OverridingController
        )
    with pytest.raises(ConfigError, match="`ApplicationController` has no `edit`"):
        Route("GET", "/a", to=ArticleController.edit, controller=ApplicationController)
    route = Route(
        "GET", "/a", to=OverridingController.index, controller=OverridingController
    )
    assert route.resolve() == (OverridingController, "index")
    # Setting `to` later is checked too.
    with pytest.raises(ConfigError):
        route.to = ApplicationController.index


def test_resource_on_a_class_that_overrides_an_action(tmp_path):
    app = make_app(tmp_path)
    app.router.resource("things")(OverridingController)
    assert TestClient(app).get("/things").body == "override"


class MethodKindsController(Controller):
    __module__ = "myapp.controllers.method_kinds_controller"

    @classmethod
    def index(cls):
        return f"classmethod on {cls.__name__}"

    @staticmethod
    def show():
        return "staticmethod"


class MethodKindsChildController(MethodKindsController):
    __module__ = "myapp.controllers.method_kinds_child_controller"


class MethodKindsOverrideController(MethodKindsController):
    __module__ = "myapp.controllers.method_kinds_override_controller"

    @classmethod
    def index(cls):
        return "override"


def test_resource_with_classmethod_and_staticmethod_actions(tmp_path):
    # A classmethod is a new bound method on each access, so the check of
    # `to` against the controller compares the functions behind them.
    app = make_app(tmp_path)
    app.router.resource("kinds")(MethodKindsController)
    app.router.resource("children")(MethodKindsChildController)
    client = TestClient(app)
    assert client.get("/kinds").body == "classmethod on MethodKindsController"
    assert client.get("/kinds/1").body == "staticmethod"
    assert client.get("/children").body == "classmethod on MethodKindsChildController"
    assert client.get("/children/1").body == "staticmethod"


def test_route_controller_with_classmethod_and_staticmethod():
    for cls in (MethodKindsController, MethodKindsChildController):
        route = Route("GET", "/a", to=cls.index, controller=cls)
        assert route.resolve() == (cls, "index")
        route = Route("GET", "/a", to=cls.show, controller=cls)
        assert route.resolve() == (cls, "show")
    # An inherited classmethod read from the parent is the same function.
    route = Route(
        "GET", "/a", to=MethodKindsController.index, controller=MethodKindsChildController
    )
    assert route.resolve() == (MethodKindsChildController, "index")
    # An overriding classmethod is still refused.
    with pytest.raises(ConfigError, match="would run"):
        Route(
            "GET",
            "/a",
            to=MethodKindsController.index,
            controller=MethodKindsOverrideController,
        )
