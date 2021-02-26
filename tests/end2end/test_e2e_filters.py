from proper import get, BaseController


class BeforeAndAfterTestCase(BaseController):
    def before_action(self, req, resp, action):
        self._f1(req, resp)
        self._f2(req, resp)
        super().before_action(req, resp, action)

    def after_action(self, req, resp, action):
        self._f1(req, resp)
        self._f2(req, resp)
        super().after_action(req, resp, action)

    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""

    def _f1(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f1-"

    def _f2(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f2-"


def test_before_and_after_filters(app, web):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


class SideEffectsTestCase(BaseController):
    def before_action(self, req, resp, action):
        resp.template = "f_custom.mako"
        super().before_action(req, resp, action)

    def rendered(self, req, resp, *args):
        resp.body = f"<html>{resp.template} was rendered</html>"


def test_custom_template_from_cb(app, web):
    app.routes = [get("", to=SideEffectsTestCase.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>f_custom.mako was rendered</html>"


class StopTestCase(BaseController):
    def before_action(self, req, resp, action):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-f1-"
        resp.stop = True
        super().before_action(req, resp, action)

    def index(self, req, resp):
        resp.headers["X-Test"] = resp.headers.get("X-Test", "") + "-index-"
        resp.body = ""


def test_stop_in_filters(app, web):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-f1-"
