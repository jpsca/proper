from proper import get, status


class FakeStartResponse:
    status: str | None = None
    headers: dict[str, str]

    def __call__(self, status, headers_list):
        self.status = status
        self.headers = dict(headers_list)


def test_call(app, Pages):
    app.routes = [get("/", to=Pages.index)]
    sr = FakeStartResponse()

    body = app({}, sr)
    assert body == [b"Hello World!"]
    assert sr.status == status.ok
    assert sr.headers["content-type"] == "text/plain; charset=utf-8"


def test_return_bytes(app, Pages):
    app.routes = [get("/", to=Pages.bytes)]
    sr = FakeStartResponse()

    body = app({}, sr)
    assert body[0] == b"bytes"


def test_catch_on_teardown_func_error(app, Pages):
    app.routes = [get("/", to=Pages.index)]
    sr = FakeStartResponse()

    @app.on_teardown
    def always_fail():
        raise ValueError

    body = app({}, sr)
    assert b"<title>Error" in body[0]
    assert sr.status == status.server_error
