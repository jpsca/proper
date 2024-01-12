from proper import View, get
from proper.current import response


def _f1(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f1-"


def _f2(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f2-"


class BeforeMiddleware:
    def before(self, view):
        response = view.response
        _f1(response.headers)
        _f2(response.headers)

    def after(self, view):
        pass


class AfterMiddleware:
    def before(self, view):
        pass

    def after(self, view):
        response = view.response
        _f1(response.headers)
        _f2(response.headers)


class BeforeAndAfterTestCase(View):
    middleware = [BeforeMiddleware, AfterMiddleware]

    def index(self):
        val = response.headers.get("x-test", "")
        response.headers["x-test"] = f"{val}-index-"
        return ""


def test_middleware(app):
    app.routes = [get("/", to=BeforeAndAfterTestCase.index)]
    resp = app.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["x-test"] == expected


class StopMiddleware:
    def before(self, view):
        response = view.response
        _f1(response.headers)
        return "STOP"

    def after(self, view):
        pass


class StopTestCase(View):
    middleware = [StopMiddleware]

    def index(self):
        val = response.headers.get("x-test", "")
        response.headers["x-test"] = f"{val}-index-"
        return ""


def test_stop_in_middleware(app):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = app.get("/")

    assert resp.headers["x-test"] == "-f1-"
