from proper import get, BaseController, before_action, after_action, around_action


class AppController(BaseController):
    def _render(self, req, resp):
        return f"<html>{resp.template} was rendered</html>"

    def f1(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f1-"

    def f2(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f2-"

    def f3(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f3-"

    def f4(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f4-"

    def f5(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f5-"

    def f6(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f6-"

    def f7(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f7-"

    def f8(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f8-"


@before_action("f1")
@before_action("f2")
@after_action("f1")
@after_action("f2")
class BeforeAndAfterTestCase(AppController):
    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_before_and_after_filters(app, web):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


@around_action("f1")
@around_action("f2")
class AroundTestCase(AppController):
    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_around_filters_applied(app, web):
    app.routes = [get("/", to=AroundTestCase.index)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


def set_greeting(req, resp):
    req.greeting = "hello"


@before_action(set_greeting)
class FiterIsExternalFunctionTestCase(AppController):
    def index(self, req, resp):
        resp.body = f"{req.greeting} world"


def test_filter_is_method_name(app, web):
    app.routes = [get("/", to=FiterIsExternalFunctionTestCase.index)]
    resp = web.get("/")
    assert resp.text == "hello world"


@before_action("f1", only=["a", "b"])
@before_action("f2", only=["b"])
class OnlyOptionTestCase(AppController):
    def a(self, req, resp):
        pass

    def b(self, req, resp):
        pass


def test_filter_applied_only_to_some_actions(app, web):
    app.routes = [
        get("a", to=OnlyOptionTestCase.a),
        get("b", to=OnlyOptionTestCase.b),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers["X-Test"] == "-f1--f2-"


@before_action("f1", skip=["b", "d"])
class SkipOptionTestCase(AppController):
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
        get("a", to=SkipOptionTestCase.a),
        get("b", to=SkipOptionTestCase.b),
        get("c", to=SkipOptionTestCase.c),
        get("d", to=SkipOptionTestCase.d),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/c").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers.get("X-Test") is None
    assert web.get("/d").headers.get("X-Test") is None


@before_action("f1", only="a")
@before_action("f2", skip="a")
class OptionsAreNotListsTestCase(AppController):
    def a(self, req, resp):
        pass

    def b(self, req, resp):
        pass


def test_filter_only_skip_no_lists(app, web):
    app.routes = [
        get("a", to=OptionsAreNotListsTestCase.a),
        get("b", to=OptionsAreNotListsTestCase.b),
    ]

    assert web.get("/a").headers["X-Test"] == "-f1-"
    assert web.get("/b").headers["X-Test"] == "-f2-"


@before_action("f1")
@before_action("fstop")
@before_action("f2")
class StopTestCase(AppController):
    def fstop(self, req, resp):
        resp.stop = True

    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_stop_in_filters(app, web):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-f1-"


@before_action("set_template")
class CustomTemplateTestCase(AppController):
    def set_template(self, req, resp):
        resp.template = "f_custom.mako"

    def rendered(self, req, resp, *args):
        pass


def test_custom_template_from_cb(app, web):
    app.routes = [get("", to=CustomTemplateTestCase.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>f_custom.mako was rendered</html>"


@around_action("f1")
@around_action("f2")
class A(AppController):
    pass


@around_action("f3")
@around_action("f4")
class B(A):
    pass


@around_action("f5")
@around_action("f6")
class C(A):
    pass


@around_action("f7")
@around_action("f8")
class InheritedTestCase(C, B):
    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_filters_are_inherited(app, web):
    app.routes = [get("/", to=InheritedTestCase.index)]
    resp = web.get("/")
    result = resp.headers["X-Test"]
    expected = "-f1--f2--f3--f4--f5--f6--f7--f8--index--f7--f8--f5--f6--f3--f4--f1--f2-"
    print("result", result)
    assert result == expected
