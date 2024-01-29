from proper import View, get
from proper.current import response


def _f1(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f1-"


def _f2(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f2-"


class BeforeConcern:
    def before(self, view):
        response = view.response
        _f1(response.headers)
        _f2(response.headers)

    def after(self, view):
        pass


class AfterConcern:
    def before(self, view):
        pass

    def after(self, view):
        response = view.response
        _f1(response.headers)
        _f2(response.headers)


class BeforeAndAfterTestCase(View):
    concerns = [BeforeConcern, AfterConcern]

    def index(self):
        val = response.headers.get("x-test", "")
        response.headers["x-test"] = f"{val}-index-"
        return ""


def test_concerns(app):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = app.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["x-test"] == expected


class StopConcern:
    def before(self, view):
        response = view.response
        _f1(response.headers)
        return "STOP"

    def after(self, view):
        pass


class StopTestCase(View):
    concerns = [StopConcern]

    def index(self):
        val = response.headers.get("x-test", "")
        response.headers["x-test"] = f"{val}-index-"
        return ""


def test_stop_in_concerns(app):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = app.get("/")

    assert resp.headers["x-test"] == "-f1-"
