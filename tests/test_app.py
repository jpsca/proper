"""Minimal end-to-end test — request in, text response out."""

import json

import pytest

from proper import App, TestClient, status
from proper.config import load_config
from proper.controller import Controller
from proper.errors import BadSecretKey, ConfigError
from proper.router import Route
from proper.units import to_seconds


class GreetController(Controller):
    def index(self):
        return "hello world"

    def show(self):
        name = self.params.get("name", "stranger")
        return f"hello {name}"


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App("tests", config)
    app.router.add_route(Route(method="GET", path="/hello", to=GreetController.index))
    app.router.add_route(Route(method="GET", path="/hello/:name", to=GreetController.show))
    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_returns_200(client):
    result = client.get("/hello")
    assert result.status == status.ok
    assert result.body == "hello world"


def test_path_param_forwarded_to_controller(client):
    result = client.get("/hello/alice")
    assert result.status == status.ok
    assert result.body == "hello alice"


def test_to_seconds():
    assert to_seconds(seconds=1) == 1
    assert to_seconds(minutes=1, seconds=3) == 63
    assert to_seconds(hours=1) == 3600
    assert to_seconds(days=1) == 86400


def test_empty_secret_keys_raises():
    with pytest.raises(ConfigError, match="SECRET_KEYS list is empty"):
        load_config({"SECRET_KEYS": []})


def test_short_secret_key_raises():
    with pytest.raises(BadSecretKey, match="not secure enough"):
        load_config({"SECRET_KEYS": ["tooshort"]})


def test_invalid_samesite_raises():
    with pytest.raises(ConfigError, match="SESSION_COOKIE_SAMESITE"):
        load_config({
            "SECRET_KEYS": ["*" * 50],
            "SESSION_COOKIE_SAMESITE": "Invalid",
        })


def test_load_config_from_class():
    class MyConfig:
        SECRET_KEYS = ["*" * 50]
        DEBUG = True

    config = load_config(MyConfig)
    assert config.SECRET_KEYS == ["*" * 50]
    assert config.DEBUG is True


# ═══════════════════════════════════════════════════════════════════
# render_importmap
# ═══════════════════════════════════════════════════════════════════


def _make_app(**overrides):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        **overrides,
    }
    app = App("tests", config)
    app.router.static("/assets", root="/tmp/assets", name="assets")
    return app


def _get_data(html: str) -> dict:
    start_json = html.find(">") + 1
    end_json = html.rfind("</script>")
    return json.loads(html[start_json:end_json])


def test_render_importmap_registered_as_global():
    app = _make_app()
    assert "render_importmap" in app.catalog.jinja_env.globals


def test_render_importmap_defaults():
    app = _make_app()
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    assert html.startswith('<script type="importmap"')
    assert html.endswith("</script>")
    data = _get_data(html)
    assert "@hotwired/stimulus" in data["imports"]
    assert "@hotwired/turbo" in data["imports"]


def test_render_importmap_resolves_asset_paths():
    app = _make_app()
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    data = _get_data(html)
    assert data["imports"]["@hotwired/stimulus"].startswith("/assets/")
    assert "stimulus.js" in data["imports"]["@hotwired/stimulus"]


def test_render_importmap_absolute_url_passthrough():
    app = _make_app(IMPORT_MAP={
        "alpinejs": "https://cdn.example.com/alpine.js",
    })
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    data = _get_data(html)
    assert data["imports"]["alpinejs"] == "https://cdn.example.com/alpine.js"


def test_render_importmap_absolute_path_passthrough():
    app = _make_app(IMPORT_MAP={
        "mylib": "/static/mylib.js",
    })
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    data = _get_data(html)
    assert data["imports"]["mylib"] == "/static/mylib.js"


def test_render_importmap_empty_config_keeps_defaults():
    """DotDict deep-merges, so IMPORT_MAP={} doesn't clear defaults."""
    app = _make_app(IMPORT_MAP={})
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    data = _get_data(html)
    assert "@hotwired/stimulus" in data["imports"]
    assert "@hotwired/turbo" in data["imports"]


def test_render_importmap_custom_entries_override_defaults():
    app = _make_app(IMPORT_MAP={
        "@hotwired/stimulus": "https://cdn.example.com/stimulus.js",
        "mylib": "js/mylib.js",
    })
    render_importmap = app.catalog.jinja_env.globals["render_importmap"]
    html = str(render_importmap())
    data = _get_data(html)
    assert data["imports"]["@hotwired/stimulus"] == "https://cdn.example.com/stimulus.js"
    assert data["imports"]["mylib"].startswith("/assets/")


def test_import_map_default_config():
    config = load_config({"SECRET_KEYS": ["*" * 50]})
    assert config.IMPORT_MAP == {
        "@hotwired/stimulus": "js/stimulus.js",
        "@hotwired/turbo": "js/turbo.js",
    }
