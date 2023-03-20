from proper import Controller, get


class BeforeAndAfterTestCase(Controller):
    def __before__(self):
        self._f1()
        self._f2()

    def __after__(self):
        self._f1()
        self._f2()

    def index(self):
        val = self.response.get_header("X-Test", "")
        self.response.set_header("X-Test", f"{val}-index-")
        self.response.body = ""

    def _f1(self):
        val = self.response.get_header("X-Test", "")
        self.response.set_header("X-Test", f"{val}-f1-")

    def _f2(self):
        val = self.response.get_header("X-Test", "")
        self.response.set_header("X-Test", f"{val}-f2-")


def test_before_and_after_filters(app, web):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = web.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["X-Test"] == expected


class SideEffectsTestCase(Controller):
    def __before__(self):
        self.response.component = "CustomComponent"

    def rendered(self, *args):
        self.response.body = f"<html>{self.response.component} was rendered</html>"


def test_custom_component_from_cb(app, web):
    app.routes = [get("", to=SideEffectsTestCase.rendered)]
    resp = web.get("/")

    assert resp.text == "<html>CustomComponent was rendered</html>"


class StopTestCase(Controller):
    def __before__(self):
        val = self.response.get_header("X-Test", "")
        self.response.set_header("X-Test", f"{val}-f1-")
        self.response.stop = True

    def index(self):
        val = self.response.get_header("X-Test", "")
        self.response.set_header("X-Test", f"{val}-index-")
        self.response.body = ""


def test_stop_in_filters(app, web):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = web.get("/")

    assert resp.headers["X-Test"] == "-f1-"
