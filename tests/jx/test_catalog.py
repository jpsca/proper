"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import time

import jinja2
import pytest

from proper.jx import Catalog, ComponentNotFoundError, FileEncodingError


def test_add_folder(folder):
    (folder / "a.jx").write_text("AAAAA")
    (folder / "b.jx").write_text("BBBBB")

    catalog = Catalog()
    catalog.add_folder(folder)

    assert "a.jx" in catalog.components
    assert "b.jx" in catalog.components

    assert catalog.components["a.jx"].base_path == folder
    assert catalog.components["a.jx"].path == folder / "a.jx"
    assert catalog.components["a.jx"].mtime == 0  # not compiled yet
    assert catalog.components["a.jx"].code is None

    assert catalog.components["b.jx"].base_path == folder
    assert catalog.components["b.jx"].path == folder / "b.jx"
    assert catalog.components["b.jx"].mtime == 0  # not compiled yet
    assert catalog.components["b.jx"].code is None


def test_has(folder):
    (folder / "a.jx").write_text("AAAAA")
    catalog = Catalog()
    catalog.add_folder(folder)

    assert catalog.has("a.jx")
    assert catalog.has("/a.jx")
    assert not catalog.has("missing.jx")


def test_add_folder_nested(tmp_path):
    folder = tmp_path / "views"
    nested = folder / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (nested / "d.jx").write_text("hello")

    catalog = Catalog(folder)

    assert catalog.components.keys() == {"a/b/c/d.jx"}


def test_add_folder_with_prefix(tmp_path):
    folder1 = tmp_path / "views1"
    folder1.mkdir()
    (folder1 / "a.jx").write_text("AAAAA")

    folder2 = tmp_path / "views2"
    folder2.mkdir()
    (folder2 / "b.jx").write_text("BBBBB")

    catalog = Catalog()
    catalog.add_folder(folder1)
    catalog.add_folder(folder2, prefix="bla")

    assert "a.jx" in catalog.components
    assert "@bla/b.jx" in catalog.components

    assert catalog.components["a.jx"].base_path == folder1
    assert catalog.components["a.jx"].path == folder1 / "a.jx"
    assert catalog.components["a.jx"].mtime == 0  # not compiled yet

    assert catalog.components["@bla/b.jx"].base_path == folder2
    assert catalog.components["@bla/b.jx"].path == folder2 / "b.jx"
    assert catalog.components["@bla/b.jx"].mtime == 0  # not compiled yet


def test_dot_in_prefix(tmp_path):
    folder = tmp_path / "views"
    folder.mkdir()
    (folder / "a.jx").write_text("AAAAA")

    catalog = Catalog()
    catalog.add_folder(folder, prefix="ui.forms")

    assert "@ui.forms/a.jx" in catalog.components

    assert catalog.components["@ui.forms/a.jx"].base_path == folder
    assert catalog.components["@ui.forms/a.jx"].path == folder / "a.jx"
    assert catalog.components["@ui.forms/a.jx"].mtime == 0  # not compiled yet


def test_add_same_folder_many_times(folder):
    (folder / "a.jx").write_text("AAAAA")
    (folder / "b.jx").write_text("BBBBB")

    catalog = Catalog()
    catalog.add_folder(folder)
    catalog.add_folder(folder)

    assert catalog.components.keys() == {"a.jx", "b.jx"}


def test_overwrite_relpath(tmp_path):
    folder1 = tmp_path / "views1"
    folder1.mkdir()
    (folder1 / "a.jx").write_text("folder1")

    folder2 = tmp_path / "views2"
    folder2.mkdir()
    (folder2 / "a.jx").write_text("folder2")

    catalog = Catalog()
    catalog.add_folder(folder1)
    catalog.add_folder(folder2)

    assert catalog.components.keys() == {"a.jx"}
    assert catalog.components["a.jx"].base_path == folder1


def test_add_same_folder_with_prefix(folder):
    (folder / "a.jx").write_text("AAAAA")

    catalog = Catalog()
    catalog.add_folder(folder)
    catalog.add_folder(folder, prefix="copy")

    assert catalog.components.keys() == {"a.jx", "@copy/a.jx"}
    assert catalog.components["a.jx"].base_path == folder
    assert catalog.components["@copy/a.jx"].base_path == folder


def test_unknown_component(folder):
    catalog = Catalog(folder)

    with pytest.raises(ComponentNotFoundError, match="Component not found: a.jx"):
        catalog.render("a.jx")

    with pytest.raises(ComponentNotFoundError, match="Component not found: b.jx"):
        catalog.get_component("b.jx")


def test_reuse_jinja_env():
    jinja_env = jinja2.Environment()
    jinja_env.filters["custom_filter"] = lambda x: f"Filtered: {x}"
    jinja_env.globals["custom_global"] = "Global Value"
    catalog = Catalog(jinja_env=jinja_env)

    assert catalog.jinja_env.filters["custom_filter"]("Test") == "Filtered: Test"
    assert catalog.jinja_env.globals["custom_global"] == "Global Value"


def test_jinja_env_preserves_user_settings():
    """Passing a jinja_env should not override its autoescape/undefined settings."""
    jinja_env = jinja2.Environment(autoescape=False, undefined=jinja2.Undefined)
    catalog = Catalog(jinja_env=jinja_env)

    assert catalog.jinja_env.autoescape is False
    assert catalog.jinja_env.undefined is jinja2.Undefined


def test_list_components(folder):
    (folder / "button.jx").write_text("<button>Click</button>")
    (folder / "card.jx").write_text("<div>Card</div>")

    catalog = Catalog(folder)
    components = catalog.list_components()

    assert isinstance(components, list)
    assert set(components) == {"button.jx", "card.jx"}


def test_list_components_empty():
    catalog = Catalog()
    components = catalog.list_components()

    assert components == []


def test_list_components_with_prefix(tmp_path):
    folder1 = tmp_path / "views1"
    folder1.mkdir()
    (folder1 / "a.jx").write_text("A")

    folder2 = tmp_path / "views2"
    folder2.mkdir()
    (folder2 / "b.jx").write_text("B")

    catalog = Catalog()
    catalog.add_folder(folder1)
    catalog.add_folder(folder2, prefix="ui")

    components = catalog.list_components()
    assert set(components) == {"a.jx", "@ui/b.jx"}


def test_get_signature(folder):
    (folder / "button.jx").write_text(
        '{#def label, size="md", disabled=False #}\n'
        '{#css "/static/button.css" #}\n'
        '{#js "/static/button.js" #}\n'
        "<button>{{ label }}</button>"
    )

    catalog = Catalog(folder)
    sig = catalog.get_signature("button.jx")

    assert sig["required"] == {"label": None}
    assert sig["optional"] == {"size": ("md", None), "disabled": (False, None)}
    assert sig["slots"] == ()
    assert sig["css"] == ("/static/button.css",)
    assert sig["js"] == ("/static/button.js",)


def test_get_signature_with_slots(folder):
    (folder / "card.jx").write_text(
        "{#def title #}\n"
        "<div>\n"
        "  <h2>{{ title }}</h2>\n"
        "  {% slot content %}Default{% endslot %}\n"
        "  {% slot footer %}{% endslot %}\n"
        "</div>"
    )

    catalog = Catalog(folder)
    sig = catalog.get_signature("card.jx")

    assert sig["required"] == {"title": None}
    assert sig["optional"] == {}
    assert sig["slots"] == ("content", "footer")
    assert sig["css"] == ()
    assert sig["js"] == ()


def test_get_signature_no_metadata(folder):
    (folder / "simple.jx").write_text("<div>Simple</div>")

    catalog = Catalog(folder)
    sig = catalog.get_signature("simple.jx")

    assert sig["required"] == {}
    assert sig["optional"] == {}
    assert sig["slots"] == ()
    assert sig["css"] == ()
    assert sig["js"] == ()


def test_get_signature_unknown_component(folder):
    catalog = Catalog(folder)

    with pytest.raises(ComponentNotFoundError, match="Component not found: unknown.jx"):
        catalog.get_signature("unknown.jx")


def test_file_encoding_error(folder):
    # Write invalid UTF-8 bytes (Latin-1 encoded text)
    (folder / "bad.jx").write_bytes(b"<div>\xe9\xe8\xe0</div>")

    catalog = Catalog(folder)

    with pytest.raises(FileEncodingError, match="Cannot read .*/bad.jx: not valid UTF-8"):
        catalog.render("bad.jx")


# ---- Asset folder / package tests ----


def test_add_folder_with_assets(tmp_path):
    components = tmp_path / "components"
    components.mkdir()
    (components / "a.jx").write_text("A")

    assets = tmp_path / "assets"
    assets.mkdir()

    catalog = Catalog()
    catalog.add_folder(components, prefix="ui", assets=assets)

    assert catalog.get_assets_folder("ui") == assets.resolve()
    assert "@ui/a.jx" in catalog.components


def test_get_assets_folder_none(tmp_path):
    components = tmp_path / "components"
    components.mkdir()
    (components / "a.jx").write_text("A")

    catalog = Catalog()
    catalog.add_folder(components, prefix="ui")

    assert catalog.get_assets_folder("ui") is None
    assert catalog.get_assets_folder("nonexistent") is None


def test_add_package(tmp_path):
    """add_package reads JX_COMPONENTS and JX_ASSETS from a module."""
    import types

    components = tmp_path / "pkg_components"
    components.mkdir()
    (components / "btn.jx").write_text("<button />")

    assets = tmp_path / "pkg_assets"
    assets.mkdir()

    # Create a fake module with JX_COMPONENTS and JX_ASSETS
    fake_mod = types.ModuleType("fake_ui_kit")
    fake_mod.JX_COMPONENTS = components
    fake_mod.JX_ASSETS = assets

    import sys
    sys.modules["fake_ui_kit"] = fake_mod
    try:
        catalog = Catalog()
        catalog.add_package("fake_ui_kit", prefix="ui")

        assert "@ui/btn.jx" in catalog.components
        assert catalog.get_assets_folder("ui") == assets.resolve()
    finally:
        del sys.modules["fake_ui_kit"]


def test_add_package_no_jx_components(tmp_path):
    """add_package raises ValueError if JX_COMPONENTS is missing."""
    import types

    fake_mod = types.ModuleType("fake_empty")
    import sys
    sys.modules["fake_empty"] = fake_mod
    try:
        catalog = Catalog()
        with pytest.raises(ValueError, match="JX_COMPONENTS"):
            catalog.add_package("fake_empty", prefix="x")
    finally:
        del sys.modules["fake_empty"]


def test_add_package_no_assets(tmp_path):
    """add_package works when JX_ASSETS is not set (assets=None)."""
    import types

    components = tmp_path / "pkg_components"
    components.mkdir()
    (components / "a.jx").write_text("A")

    fake_mod = types.ModuleType("fake_no_assets")
    fake_mod.JX_COMPONENTS = components

    import sys
    sys.modules["fake_no_assets"] = fake_mod
    try:
        catalog = Catalog()
        catalog.add_package("fake_no_assets", prefix="na")

        assert "@na/a.jx" in catalog.components
        assert catalog.get_assets_folder("na") is None
    finally:
        del sys.modules["fake_no_assets"]


def test_collect_assets(tmp_path):
    """collect_assets copies files from assets dirs to output."""
    components = tmp_path / "components"
    components.mkdir()
    (components / "a.jx").write_text("A")

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "button.css").write_text(".btn {}")
    sub = assets / "sub"
    sub.mkdir()
    (sub / "card.css").write_text(".card {}")

    output = tmp_path / "output"

    catalog = Catalog()
    catalog.add_folder(components, prefix="ui", assets=assets)
    collected = catalog.collect_assets(output)

    assert len(collected) == 2
    prefixes = [c[0] for c in collected]
    assert all(p == "ui" for p in prefixes)

    assert (output / "ui" / "button.css").read_text() == ".btn {}"
    assert (output / "ui" / "sub" / "card.css").read_text() == ".card {}"


def test_collect_assets_multiple_prefixes(tmp_path):
    """collect_assets handles multiple prefixes."""
    comp1 = tmp_path / "comp1"
    comp1.mkdir()
    (comp1 / "a.jx").write_text("A")

    assets1 = tmp_path / "assets1"
    assets1.mkdir()
    (assets1 / "a.css").write_text("a")

    comp2 = tmp_path / "comp2"
    comp2.mkdir()
    (comp2 / "b.jx").write_text("B")

    assets2 = tmp_path / "assets2"
    assets2.mkdir()
    (assets2 / "b.css").write_text("b")

    output = tmp_path / "output"

    catalog = Catalog()
    catalog.add_folder(comp1, prefix="one", assets=assets1)
    catalog.add_folder(comp2, prefix="two", assets=assets2)
    catalog.collect_assets(output)

    assert (output / "one" / "a.css").read_text() == "a"
    assert (output / "two" / "b.css").read_text() == "b"


def test_assets_without_prefix_raises(tmp_path):
    components = tmp_path / "components"
    components.mkdir()
    (components / "a.jx").write_text("A")

    assets = tmp_path / "assets"
    assets.mkdir()

    catalog = Catalog()
    with pytest.raises(ValueError, match="Cannot register assets folder without a prefix"):
        catalog.add_folder(components, assets=assets)


def test_render(folder):
    (folder / "hello.jx").write_text("{#def name #}\n<p>Hello {{ name }}</p>")

    catalog = Catalog(folder)
    html = catalog.render("hello.jx", name="World")

    assert "<p>Hello World</p>" in html


def test_render_string():
    catalog = Catalog()
    html = catalog.render_string("{#def x #}\n<b>{{ x }}</b>", x="hi")

    assert "<b>hi</b>" in html


def test_auto_reload_false_cache(folder):
    (folder / "a.jx").write_text("<p>cached</p>")

    catalog = Catalog(folder, auto_reload=False)
    # First call compiles; second call returns cached code
    cdata1 = catalog.get_component_data("a.jx")
    cdata2 = catalog.get_component_data("a.jx")

    assert cdata1 is cdata2
    assert cdata1.code is not None


def test_asset_resolver_invoked(tmp_path):
    components = tmp_path / "components"
    components.mkdir()
    (components / "btn.jx").write_text(
        '{#css "btn.css" #}\n<button>click</button>\n{{ assets.render_css() }}'
    )

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "btn.css").write_text(".btn{}")

    catalog = Catalog(
        asset_resolver=lambda url, prefix: f"/pkg/{prefix}/{url}",
    )
    catalog.add_folder(components, prefix="ui", assets=assets)
    html = catalog.render("@ui/btn.jx")

    assert "/pkg/ui/btn.css" in html


def test_asset_resolver_skipped_without_assets_folder(tmp_path):
    """Resolver is not called for prefixes without a registered assets folder."""
    components = tmp_path / "components"
    components.mkdir()
    (components / "btn.jx").write_text(
        '{#css "btn.css" #}\n<button />\n{{ assets.render_css() }}'
    )

    catalog = Catalog(
        asset_resolver=lambda url, prefix: f"/pkg/{prefix}/{url}",
    )
    # No assets= argument, so resolver should NOT transform the URL
    catalog.add_folder(components, prefix="ui")
    html = catalog.render("@ui/btn.jx")

    assert "btn.css" in html
    assert "/pkg/" not in html


def test_auto_reload_recompiles_on_change(folder):
    comp = folder / "a.jx"
    comp.write_text("<p>v1</p>")

    catalog = Catalog(folder, auto_reload=True)
    html1 = catalog.render("a.jx")
    assert "v1" in html1

    # Modify the file (ensure mtime changes)
    time.sleep(0.05)
    comp.write_text("<p>v2</p>")

    html2 = catalog.render("a.jx")
    assert "v2" in html2


def test_render_string_does_not_share_assets_between_sources(folder):
    """
    Every string component is named `<string>`, so caching its collected
    assets under that name would serve one source's CSS/JS to every other.
    `render_string` is documented as not cached, so it must not use the cache.
    """
    catalog = Catalog(folder)

    assert catalog.render_string(
        '{#css "a.css" #}{#js "a.js" #}\n{{ assets.render() }}'
    ) == '<link rel="stylesheet" href="a.css">\n<script type="module" src="a.js"></script>'

    assert catalog.render_string(
        '{#css "b.css" #}{#js "b.js" #}\n{{ assets.render() }}'
    ) == '<link rel="stylesheet" href="b.css">\n<script type="module" src="b.js"></script>'


@pytest.mark.parametrize(
    "source, expected",
    [
        ("{% raw %}Use {% in a sentence{% endraw %}", "Use {% in a sentence"),
        ('{% raw %}{% "unterminated quote{% endraw %}', '{% "unterminated quote'),
        ("{% raw %}<Card />{%+ endraw %}", "<Card />"),
    ],
)
def test_raw_blocks_render_exactly_like_jinja(folder, source, expected):
    """A raw block is text all the way down, so Jx must not lex inside it."""
    catalog = Catalog(folder)
    assert catalog.render_string(source) == expected
    assert jinja2.Environment().from_string(source).render() == expected


def test_auto_reload_recompiles_child_on_change(folder):
    """
    A child component is resolved through `get_component_data`, which is what
    stats its file. Remembering the resolved child on the parent skips that
    stat, so with auto-reload on it must not be remembered.
    """
    (folder / "child.jx").write_text("<p>v1</p>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    catalog = Catalog(folder, auto_reload=True)
    assert "v1" in catalog.render("parent.jx")

    time.sleep(0.05)  # ensure the mtime actually changes
    (folder / "child.jx").write_text("<p>v2</p>")

    assert "v2" in catalog.render("parent.jx")


def test_auto_reload_false_caches_children(folder):
    (folder / "child.jx").write_text("<p>hi</p>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    catalog = Catalog(folder, auto_reload=False)
    # Twice: compiling the child drops the catalog's component cache, so after
    # the first render the parent instance held here is already superseded.
    catalog.render("parent.jx")
    catalog.render("parent.jx")
    parent = catalog.get_component("parent.jx")

    assert parent._child_cache == {"Child": catalog.get_component("child.jx")}


def test_enabling_auto_reload_invalidates_cached_children(folder):
    """
    Components built while auto-reload was off remember their children. Turning
    it back on has to discard them, or those instances go on ignoring edits.
    """
    (folder / "child.jx").write_text("<p>v1</p>")
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}\n<div><Child /></div>'
    )

    catalog = Catalog(folder, auto_reload=False)
    assert "v1" in catalog.render("parent.jx")

    catalog.auto_reload = True
    time.sleep(0.05)
    (folder / "child.jx").write_text("<p>v2</p>")

    assert "v2" in catalog.render("parent.jx")


def test_auto_reload_setter_is_a_noop_when_unchanged(folder):
    (folder / "a.jx").write_text("<p>hi</p>")
    catalog = Catalog(folder, auto_reload=False)
    catalog.render("a.jx")
    before = catalog.get_component("a.jx")

    catalog.auto_reload = False

    assert catalog.get_component("a.jx") is before
