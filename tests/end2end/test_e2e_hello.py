import pytest

from proper import App, BadSecretKey, Controller, get, status


class MyController(Controller):
    def render(self):
        return "whatever"

    def index(self):
        self.response.body = "Hello Callable!"

    def echo_query(self):
        self.response.headers["rec-query"] = "|".join(
            [
                f"{key}:{','.join(str(val) for val in values)}"
                for key, values in self.request.query.items()
            ]
        )


def test_hello_world(app, Pages, web):
    app.routes = [get("/", to=Pages.index)]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"
    assert resp.content_type == "text/plain"


def test_proxied_routes(app, Pages):
    app.routes = [get("/", to=Pages.index)]

    assert app.router.routes == app.routes


def test_hello_callable(app, web):
    app.routes = [get("/", to=MyController.index)]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello Callable!"


def test_default_config(app):
    assert app.config.catch_all_errors


def test_load_config(app):
    assert app.config.lorem == "ipsum"


def test_secret_key_too_short(import_name):
    with pytest.raises(BadSecretKey):
        App(import_name, config={"secret_keys": ["qwertyuiop"]})


def test_head(app, Pages, web):
    app.routes = [get("/", to=Pages.index)]
    resp = web.head("/")

    assert resp.status == status.ok
    assert resp.text == ""


def test_charset(app, Pages, web):
    app.routes = [get("/", to=Pages.charset)]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"
    assert resp.content_type == "text/html"


def test_req_query(app, web):
    app.routes = [get("/", to=MyController.echo_query)]
    resp = web.get("/?foo=bar&ok&color=red&color=green&color=blue")

    assert resp.status == status.ok
    assert resp.headers["rec-query"] == "foo:bar|ok:|color:red,green,blue"
