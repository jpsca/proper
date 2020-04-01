import pytest

from proper import (
    App,
    BaseController,
    scope,
    get,
    status,
    BadSecretKey,
)


class MyController(BaseController):
    def _render(self, req, resp):
        return "whatever"

    def index(self, req, resp):
        resp.body = "Hello Callable!"

    def echo_query(self, req, resp):
        resp.headers["req-query"] = "|".join(
            [
                f"{key}:{','.join(str(val) for val in values)}"
                for key, values in req.query.items()
            ]
        )


def test_hello_world(app, web):
    app.routes = [scope("/")(get("/", to="Pages.index"))]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"
    assert resp.content_type == "text/plain"


def test_proxied_routes(app):
    app.routes = [scope("/")(get("/", to="Pages.index"))]

    assert app.router.routes == app.routes


def test_hello_callable(app, web):
    app.routes = [scope("/")(get("/", to=MyController.index))]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello Callable!"


def test_default_config(root_path):
    app = App(root_path)
    assert app.config.catch_all_errors


def test_multiple_configs(root_path):
    app = App(root_path, config=[{"a": 1}, {"b": 2}])
    assert app.config.a == 1
    assert app.config.b == 2


def test_serializer(app):
    assert "secret_key" in app.config
    assert app.serializer


def test_no_secret_key_no_serializer(root_path):
    app = App(root_path)
    assert "secret_key" not in app.config
    assert getattr(app, "serializer", None) is None


def test_add_secret_key_to_add_serializer(root_path):
    app = App(root_path)

    assert getattr(app, "serializer", None) is None
    app.setup({"secret_key": "a" * 60})
    assert getattr(app, "serializer", None)


def test_secret_key_too_short(root_path):
    with pytest.raises(BadSecretKey):
        App(root_path, config={"secret_key": "qwertyuiop"})


def test_load_config_file(assets_path, root_path):
    config_path = assets_path / "config.yaml"
    app = App(root_path, config=config_path)

    assert app.config.hello == "world"
    assert app.config.secret_key.startswith("Not secure.")


def test_load_secrets_file(assets_path, root_path):
    config_path = assets_path / "config.yaml"
    secrets_path = assets_path / "secrets.yaml.enc"
    app = App(root_path, config=config_path, secrets=secrets_path)

    assert app.config.hello == "world"
    assert app.config.secret_key is not None


def test_head(app, web):
    app.routes = [scope("/")(get("/", to="Pages.index"))]
    resp = web.head("/")

    assert resp.status == status.ok
    assert resp.text == ""


def test_redirect_to(app, web):
    app.routes = [scope("/")(get("/", to="Pages.redirect"))]
    resp = web.get("/")

    assert resp.status == status.see_other
    assert resp.headers["Location"] == "http://example.com"


def test_json(app, web):
    app.routes = [scope("/")(get("/", to="Pages.json"))]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.headers["Content-Type"] == "application/json; charset=utf-8"
    assert resp.text == """{"Hello":"World"}"""


def test_charset(app, web):
    app.routes = [scope("/")(get("/", to="Pages.charset"))]
    resp = web.get("/")

    assert resp.status == status.ok
    assert resp.text == "Hello World!"
    assert resp.headers["Content-Type"] == "text/html; charset=latin1"


def test_req_query(app, web):
    app.routes = [scope("/")(get("/", to=MyController.echo_query))]
    resp = web.get("/?foo=bar&ok&color=red&color=green&color=blue")

    assert resp.status == status.ok
    assert resp.headers["req-query"] == "foo:bar|ok:True|color:red,green,blue"
