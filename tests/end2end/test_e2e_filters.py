from proper import get, BaseController, before_action, after_action


class AppController(BaseController):
    def _render(self, req, resp):
        return f"<html>{resp.template} was rendered</html>"


def f1(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f1-"


def f2(_req, resp, _app):
    resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f2-"


@before_action(f1)
@before_action(f2)
@after_action(f1)
@after_action(f2)
class HasFilters(AppController):
    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_filters_applied(app, web):
    app.routes = [get("/", to=HasFilters.append)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


@before_action("set_greeting")
class HasMethodFilter(AppController):
    def set_greeting(self, req, resp, app):
        self.greeting = "hello"

    def index(self, req, resp):
        resp.body = f"{self.greeting} world"

def test_method_filter(app, web):
    app.routes = [get("/", to=HasMethodFilter.index)]
    resp = web.get("/")
    assert resp.text == "hello world"


@before_action(f1, only=["a", "b"])
@before_action(f2, only=["b"])
class HasOnlyFilters(AppController):
    def a(self, req, resp):
        pass

    def b(self, req, resp):
        pass


def test_filter_applied_only_to_some_actions(app, web):
    app.routes = [
        get("a", to=HasOnlyFilters.a),
        get("b", to=HasOnlyFilters.b),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers["X-Test"] == "-f1--f2-"


@before_action(f1, skip=["b", "d"])
class HasSkipFilter(AppController):
    def a(self, req, resp):
        pass

    def b(self, req, resp):
        pass

    def c(self, req, resp):
        pass

    def d(self, req, resp):
        pass


def test_filter_skip_some_actions(app, web):
    app.routes = [
        get("a", to=HasSkipFilter.a),
        get("b", to=HasSkipFilter.b),
        get("c", to=HasSkipFilter.c),
        get("d", to=HasSkipFilter.d),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/c").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers.get("X-Test") is None
    assert web.get("/d").headers.get("X-Test") is None


@before_action(f1, only="a")
@before_action(f2, skip="a")
class HasOnlySkipNoListsFilter(AppController):
    def a(self, req, resp):
        pass

    def b(self, req, resp):
        pass


def test_filter_only_skip_no_lists(app, web):
    app.routes = [
        get("a", to=HasOnlySkipNoListsFilter.a),
        get("b", to=HasOnlySkipNoListsFilter.b),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers["X-Test"] == "-f2-"


def filter_stop(_req, resp, _app):
    resp.stop = True


@before_action(f1)
@before_action(filter_stop)
@before_action(f2)
class HasStopFilter(AppController):
    def append(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_stop_in_filters(app, web):
    app.routes = [get("/", to=HasStopFilter.append)]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-f1-"


def filter_set_template(req, resp, _app):
    resp.template = "f_custom.mako"


@before_action(filter_set_template)
class CustomTemplateFromFilter(AppController):
    def rendered(self, req, resp, *args):
        pass


def test_custom_template_from_cb(app, web):
    app.routes = [get("", to=CustomTemplateFromFilter.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>f_custom.mako was rendered</html>"
