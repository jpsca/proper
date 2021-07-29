from proper import get, status


class FakeStartResponse:
    status_code = headers_list = None

    def __call__(self, status_code, headers_list):
        self.status_code = status_code
        self.headers = dict(headers_list)


def test_call(app, Pages):
    app.routes = [get("/", to=Pages.index)]
    start_response = FakeStartResponse()
    body = app({}, start_response)

    assert body == [b"Hello World!"]
    assert start_response.status_code == status.ok
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_pipefinal_error(app, Pages):
    app.routes = [get("/", to=Pages.index)]

    @app.on_teardown
    def on_fail(req, resp, app):
        raise ValueError

    start_response = FakeStartResponse()
    body = app({}, start_response)

    assert b"<title>Error</title>" in body[0]
    assert start_response.status_code == status.server_error
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_return_bytes(app, Pages):
    app.routes = [get("/", to=Pages.bytes)]

    start_response = FakeStartResponse()
    body = app({}, start_response)

    assert body[0] == b"bytes"
