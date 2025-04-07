from proper import Controller


def _f1(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f1-"


def _f2(headers):
    val = headers.get("x-test", "")
    headers["x-test"] = f"{val}-f2-"


def before_concern(co):
    response = co.response
    _f1(response.headers)
    _f2(response.headers)


def after_concern(co):
    response = co.response
    _f1(response.headers)
    _f2(response.headers)


class BeforeAndAfterTestCase(Controller):
    before = [before_concern]
    after = [after_concern]

    def index(self):
        val = self.response.headers.get("x-test", "")
        self.response.headers["x-test"] = f"{val}-index-"
        return ""


def test_concerns(app):
    app.router.get("/")(BeforeAndAfterTestCase.index)
    resp = app.get("/")
    expected = "-f1--f2--index--f1--f2-"
    assert resp.headers["x-test"] == expected


def stop_concern(co):
    response = co.response
    _f1(response.headers)
    return "STOP"


class StopTestCase(Controller):
    before = [stop_concern]

    def index(self):
        val = self.response.headers.get("x-test", "")
        self.response.headers["x-test"] = f"{val}-index-"
        return ""


def test_stop_in_concerns(app):
    app.router.get("/")(StopTestCase.index)
    resp = app.get("/")

    assert resp.headers["x-test"] == "-f1-"
