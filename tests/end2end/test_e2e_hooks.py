from proper import get, status


def test_catch_on_teardown_func_error(app, Pages, start_response):
    app.routes = [get("/", to=Pages.index)]

    @app.on_teardown
    def always_fail(request, response):
        raise ValueError

    body = app({}, start_response)

    assert b"<title>Error" in body[0]
    assert start_response.status_code == status.server_error
    assert start_response.content_type == "text/plain; charset=utf-8"
