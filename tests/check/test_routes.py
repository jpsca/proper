from proper.check import ERROR, WARNING, Problem
from proper.check.routes import (
    check_controllers,
    check_routes,
    check_views,
    compiler_problems,
)
from proper.router import Route
from .conftest import extend


def test_a_controller_that_cant_be_loaded(make_shop):
    app = make_shop(extend("shop/controllers.py", """

        def make():
            class HiddenController(Controller):
                @router.get("hidden")
                def index(self):
                    pass

        make()
    """))
    [problem] = check_controllers(app)
    assert problem.level == ERROR
    assert "the controller of the route GET /hidden can't be loaded" in problem.message
    assert problem.path == "shop/controllers.py"
    assert problem.line == 22  # the decorators of `index`


def test_a_callback_that_is_not_a_method(make_shop):
    app = make_shop(extend("shop/controllers.py", """

        class OrderController(Controller):
            before = {"do": "load_order"}

            @router.get("orders")
            @router.get("orders/all")
            def index(self):
                pass
    """))
    [problem] = check_controllers(app)
    assert problem.message == (
        "OrderController: `before` callback `load_order` is not a method of the controller"
    )
    assert (problem.path, problem.line) == ("shop/controllers.py", 20)


def test_a_view_that_does_not_compile(make_shop):
    app = make_shop({"shop/views/post/show.jx": "<h1>Post</h1>\n<Card />\n"})
    [problem] = check_views(app)
    assert problem.level == ERROR
    assert problem.path == "shop/views/post/show.jx"
    assert problem.line == 2
    assert "`Card` is not imported" in problem.message


def test_views_without_a_compiler(make_shop):
    app = make_shop()
    app.catalog.compiler = None
    [problem] = check_views(app)
    assert problem.level == WARNING
    assert "no views compiler" in problem.message


def test_compiler_problems():
    output = "/elsewhere/a.jx:3:7: Bad tag\n\nsomething else\n/elsewhere/a.jx:3:7: Bad tag\n"
    assert compiler_problems(output) == [
        Problem(ERROR, "Bad tag", path="/elsewhere/a.jx", line=3, col=7),
        Problem(ERROR, "something else"),
    ]


def test_a_route_that_never_matches(make_shop):
    app = make_shop(extend("shop/controllers.py", """

        class OtherController(Controller):
            @router.get("posts")
            def index(self):
                pass
    """))
    [problem] = check_routes(app)
    assert problem.level == ERROR
    assert problem.message == (
        "the route GET /posts never matches: an earlier route has the same "
        "method, path and host (`Post.index`)"
    )
    assert (problem.path, problem.line) == ("shop/controllers.py", 21)


def test_a_name_with_two_paths(make_shop):
    app = make_shop(extend("shop/controllers.py", """

        class OtherController(Controller):
            @router.get("others", name="Post.index")
            def index(self):
                pass
    """))
    [problem] = check_routes(app)
    assert problem.message == (
        "the name `Post.index` is also used by the route GET /posts; `url_for` builds that one"
    )


def test_routes_without_a_controller(make_shop):
    """Redirects and the routes only for `url_for` have no controller; the
    same path on another host is another route."""
    app = make_shop()
    router = app.router
    router.get("old-posts", redirect="/posts")
    router.get("old-posts", redirect="/posts", name="Old.posts")
    router.add_route(Route("GET", "/posts", name="Post.index"))
    router.add_route(Route("GET", "/posts", name="Admin.posts", host="admin.example.com"))
    router.add_route(Route("GET", "/drafts", name="Admin.posts", host="admin.example.com"))
    assert check_routes(app) == [
        Problem(
            ERROR,
            "the route GET /old-posts never matches: an earlier route has the "
            "same method, path and host",
        ),
        Problem(
            ERROR,
            "the name `Admin.posts` is also used by the route GET /posts "
            "(host admin.example.com); `url_for` builds that one",
        ),
    ]
    assert check_controllers(app) == []
