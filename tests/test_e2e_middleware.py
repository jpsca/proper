from proper import Controller


def _f1(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f1-"


def _f2(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f2-"


class BeforeConcern:
    def before(self, co):
        response = co.response
        _f1(response.headers)
        _f2(response.headers)

    def after(self, view):
        pass


class AfterConcern:
    def before(self, co):
        pass

    def after(self, co):
        response = co.response
        _f1(response.headers)
        _f2(response.headers)


class BeforeAndAfterTestCase(Controller):
    concerns = [BeforeConcern, AfterConcern]

    def index(self):
        val = self.response.headers.get("x-test", "")
        self.response.headers["x-test"] = f"{val}-index-"
        return ""


def test_concerns(app):
    app.router.get("/")(BeforeAndAfterTestCase.index)
    resp = app.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["x-test"] == expected


class StopConcern:
    def before(self, co):
        response = co.response
        _f1(response.headers)
        return "STOP"

    def after(self, co):
        pass


class StopTestCase(Controller):
    concerns = [StopConcern]

    def index(self):
        val = self.response.headers.get("x-test", "")
        self.response.headers["x-test"] = f"{val}-index-"
        return ""


def test_stop_in_concerns(app):
    app.router.get("/")(StopTestCase.index)
    resp = app.get("/")

    assert resp.headers["x-test"] == "-f1-"
