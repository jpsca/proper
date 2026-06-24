import json

from proper import App
from proper.core.config import load_config


def _make_app(**overrides):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
        **overrides,
    }
    app = App(__name__, config)
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
        "@hotwired/stimulus": "js/vendor/stimulus.js",
        "@hotwired/turbo": "js/vendor/turbo.js",
    }
