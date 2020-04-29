from proper import forward
from proper import get
from proper import make_test_environ
from proper import scope
from proper import status


class FakeStartResponse(object):
    status_code = headers_list = None

    def __call__(self, status_code, headers_list):
        self.status_code = status_code
        self.headers = dict(headers_list)


def test_call(app):
    app.routes = [scope("/")(get("/", to="Pages.index"))]
    start_response = FakeStartResponse()
    env = make_test_environ()
    body = app(env, start_response)

    assert body == [b"Hello World!"]
    assert start_response.status_code == status.ok
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_pipefinal_error(app):
    app.routes = [scope("/")(get("/", to="Pages.index"))]

    @app.on_teardown
    def plug_fail(_req, _resp, _app):
        raise ValueError

    start_response = FakeStartResponse()
    env = make_test_environ()
    body = app(env, start_response)

    assert b"<title>Error</title>" in body[0]
    assert start_response.status_code == status.server_error
    assert start_response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_forward(app):
    def echo(env, start_response):
        return (env, start_response)

    app.routes = [forward("/", to=echo)]
    start_response = FakeStartResponse()
    env = make_test_environ()

    resp_env, resp_sr = app(env, start_response)
    assert resp_env == env
    assert resp_sr == start_response
