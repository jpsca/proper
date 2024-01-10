from proper import Controller, get
from proper.current import response


def _f1(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f1-"


def _f2(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f2-"


class BeforeMiddleware:
    def before(self, controller):
        _f1(response.headers)
        _f2(response.headers)

    def after(self, controller):
        pass


class AfterMiddleware:
    def before(self, controller):
        pass

    def after(self, controller):
        _f1(response.headers)
        _f2(response.headers)


class BeforeAndAfterTestCase(Controller):
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
    def before(self, controller):
        _f1(response.headers)
        return "STOP"

    def after(self, controller):
        pass


class StopTestCase(Controller):
    middleware = [StopMiddleware]

    def index(self):
        val = response.headers.get("x-test", "")
        response.headers["x-test"] = f"{val}-index-"
        return ""


def test_stop_in_middleware(app):
    app.routes = [get("/", to=StopTestCase.index)]
    resp = app.get("/")

    assert resp.headers["x-test"] == "-f1-"
