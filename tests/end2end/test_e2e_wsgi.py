from proper import get, status


def test_call(app, Pages, start_response):
    app.routes = [get("/", to=Pages.index)]
    body = app({}, start_response)

    assert body == [b"Hello World!"]
    assert start_response.status_code == status.ok
    assert start_response.set_content_type("text/plain")


def test_return_bytes(app, Pages, start_response):
    app.routes = [get("/", to=Pages.bytes)]

    body = app({}, start_response)

    assert body[0] == b"bytes"
