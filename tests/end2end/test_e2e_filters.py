from proper import Controller, get


class BeforeAndAfterTestCase(Controller):
    def before_action(self):
        self._f1()
        self._f2()

    def after_action(self):
        self._f1()
        self._f2()

    def index(self):
        self.response.headers["X-Test"] = self.response.headers.get("X-Test", "") + "-index-"
        self.response.body = ""

    def _f1(self):
        self.response.headers["X-Test"] = self.response.headers.get("X-Test", "") + "-f1-"

    def _f2(self):
        self.response.headers["X-Test"] = self.response.headers.get("X-Test", "") + "-f2-"


def test_before_and_after_filters(app, web):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


class SideEffectsTestCase(Controller):
    def before_action(self):
        self.response.template = "f_custom.mako"

    def rendered(self, *args):
        self.response.body = f"<html>{self.response.template} was rendered</html>"


def test_custom_template_from_cb(app, web):
    app.routes = [get("", to=SideEffectsTestCase.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>f_custom.mako was rendered</html>"


class StopTestCase(Controller):
    def before_action(self):
        self.response.headers["X-Test"] = self.response.headers.get("X-Test", "") + "-f1-"
        self.response.stop = True

    def index(self):
        self.response.headers["X-Test"] = self.response.headers.get("X-Test", "") + "-index-"
        self.response.body = ""


def test_stop_in_filters(app, web):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-f1-"
