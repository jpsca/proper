import pytest

from proper import App, BadSecretKey, BaseController, get, status


class MyController(BaseController):
    def render(self):
        return "whatever"

    def index(self):
        self.resp.body = "Hello Callable!"

    def echo_query(self):
        self.resp.headers["req-query"] = "|".join(
            [
                f"{key}:{','.join(str(val) for val in values)}"
                for key, values in self.req.query.items()
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


def test_default_config(import_name):
    app = App(import_name)
    assert app.config.catch_all_errors


def test_serializer(app):
    assert "secret_key" in app.config
    assert app.serializer


def test_no_secret_key_no_serializer(import_name):
    app = App(import_name)
    assert "secret_key" not in app.config
    assert getattr(app, "serializer", None) is None


def test_add_secret_key_to_add_serializer(import_name):
    app = App(import_name)

    assert getattr(app, "serializer", None) is None
    app.update_config({"secret_key": "a" * 60})
    assert getattr(app, "serializer", None)


def test_secret_key_too_short(import_name):
    with pytest.raises(BadSecretKey):
        App(import_name, config={"secret_key": "qwertyuiop"})


def test_head(app, Pages, web):
    app.routes = [get("/", to=Pages.index)]
    resp = web.head("/")

    assert resp.status == status.ok
    assert resp.text == ""


def test_json(app, Pages, web):
    app.routes = [get("/", to=Pages.json)]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.headers["Content-Type"] == "application/json; charset=utf-8"
    assert resp.text == """{"Hello": "World"}"""


def test_charset(app, Pages, web):
    app.routes = [get("/", to=Pages.charset)]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"
    assert resp.headers["Content-Type"] == "text/html; charset=latin1"


def test_req_query(app, web):
    app.routes = [get("/", to=MyController.echo_query)]
    resp = web.get("/?foo=bar&ok&color=red&color=green&color=blue")

    assert resp.status == status.ok
    assert resp.headers["req-query"] == "foo:bar|ok:True|color:red,green,blue"
