from proper import get, make_test_environ, status


class FakeStartResponse:
    status_code = headers_items = None

    def __call__(self, status_code, headers_items):
        self.status_code = status_code
        self.headers = dict(headers_items)


def test_call(app):
    app.routes = [get("/", to="Pages.index")]
    start_response = FakeStartResponse()
    env = make_test_environ()
    body = app(env, start_response)

    assert body == [b"Hello World!"]
    assert start_response.status_code == status.ok
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_pipefinal_error(app):
    app.routes = [get("/", to="Pages.index")]

    @app.on_teardown
    def on_fail(_req, _resp, _app):
        raise ValueError

    start_response = FakeStartResponse()
    env = make_test_environ()
    body = app(env, start_response)

    assert b"<title>Error</title>" in body[0]
    assert start_response.status_code == status.server_error
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"
