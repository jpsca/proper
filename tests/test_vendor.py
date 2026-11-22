"""The code that downloads the vendored JS and CSS files: the Hotwire
libraries of new apps, and the editor of the rich text addon.

The downloads are served by a local server, with small files that have
what the real ones have.
"""
import importlib
import runpy
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from proper import vendor


# `proper.vendor.lexxy` and `proper.vendor.hotwire` are the functions:
# the modules, with the URLs, are these.
lexxy = importlib.import_module("proper.vendor.lexxy")
hotwire = importlib.import_module("proper.vendor.hotwire")


REPO_ROOT = Path(__file__).resolve().parent.parent
RICH_TEXT_BLUEPRINT = REPO_ROOT / "src" / "proper" / "_blueprints" / "addon_rich_text"

LEXXY_VERSIONS = {"@37signals/lexxy": "1.2.3", "@rails/activestorage": "4.5.6"}
HOTWIRE_VERSIONS = {"@hotwired/stimulus": "1.1.1", "@hotwired/turbo": "2.2.2"}

LEXXY_BUNDLE = (
    b"/* esm.sh - @37signals/lexxy@1.2.3 */\n"
    b'import{a}from"./helpers.mjs";import"/lexical@^0.44.0/Lexical.prod?target=es2022";'
    b'let{DirectUpload:e}=await import("/@rails/activestorage@>=%207.0.0?target=es2022");\n'
    b"//# sourceMappingURL=lexxy.bundle.mjs.map"
)
LEXXY_HELPERS = (
    b'import"/prismjs@^1.30.0?target=es2022";export{a};\n'
    b"//# sourceMappingURL=helpers.mjs.map"
)
ACTIVESTORAGE = (
    b"/* esm.sh - @rails/activestorage@4.5.6 */\n"
    b"var R=1;export{R as DirectUpload};\n"
    b"//# sourceMappingURL=activestorage.mjs.map"
)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture()
def cdn(tmp_path):
    """A local server for the files of the folder it returns with its URL."""
    folder = tmp_path / "cdn"
    folder.mkdir()
    handler = partial(QuietHandler, directory=str(folder))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield folder, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture()
def lexxy_cdn(cdn, monkeypatch):
    folder, url = cdn
    (folder / "lexxy-1.2.3.mjs").write_bytes(LEXXY_BUNDLE)
    (folder / "helpers-1.2.3.mjs").write_bytes(LEXXY_HELPERS)
    (folder / "activestorage-4.5.6.mjs").write_bytes(ACTIVESTORAGE)
    css = folder / "css-1.2.3"
    css.mkdir()
    for name in lexxy.CSS_SOURCES:
        (css / name).write_text(f"/* {name} */\n")

    monkeypatch.setattr(lexxy, "JS_URL", url + "/lexxy-{version}.mjs")
    monkeypatch.setattr(lexxy, "HELPERS_URL", url + "/helpers-{version}.mjs")
    monkeypatch.setattr(lexxy, "ACTIVESTORAGE_URL", url + "/activestorage-{version}.mjs")
    monkeypatch.setattr(lexxy, "CSS_BASE", url + "/css-{version}")
    return folder


class TestLexxy:
    def test_writes_the_files(self, lexxy_cdn, tmp_path):
        target = tmp_path / "assets"
        vendor.lexxy(str(target), LEXXY_VERSIONS)

        assert sorted(p.name for p in (target / "js" / "vendor").iterdir()) == [
            "activestorage.js",
            "lexxy-helpers.js",
            "lexxy.js",
        ]
        assert sorted(p.name for p in (target / "css").iterdir()) == sorted(
            lexxy.CSS_SOURCES
        )

    def test_the_bundle_imports_activestorage_by_name(self, lexxy_cdn, tmp_path):
        vendor.lexxy(tmp_path, LEXXY_VERSIONS)
        js = (tmp_path / "js" / "vendor" / "lexxy.js").read_text()

        assert 'await import("activestorage")' in js
        assert "@rails/activestorage" not in js

    def test_the_other_imports_point_to_esm_sh(self, lexxy_cdn, tmp_path):
        vendor.lexxy(tmp_path, LEXXY_VERSIONS)
        js = (tmp_path / "js" / "vendor" / "lexxy.js").read_text()
        helpers = (tmp_path / "js" / "vendor" / "lexxy-helpers.js").read_text()

        assert 'import"https://esm.sh/lexical@^0.44.0/Lexical.prod?target=es2022"' in js
        assert 'from"./lexxy-helpers.js"' in js
        assert 'import"https://esm.sh/prismjs@^1.30.0?target=es2022"' in helpers

    def test_the_source_map_references_are_removed(self, lexxy_cdn, tmp_path):
        vendor.lexxy(tmp_path, LEXXY_VERSIONS)

        for path in (tmp_path / "js" / "vendor").iterdir():
            assert "sourceMappingURL" not in path.read_text()

    def test_activestorage_is_saved_as_it_is(self, lexxy_cdn, tmp_path):
        vendor.lexxy(tmp_path, LEXXY_VERSIONS)
        js = (tmp_path / "js" / "vendor" / "activestorage.js").read_text()

        assert js.startswith("/* esm.sh - @rails/activestorage@4.5.6 */\n")
        assert "export{R as DirectUpload};" in js

    def test_the_css_gets_the_rules_of_proper(self, lexxy_cdn, tmp_path):
        vendor.lexxy(tmp_path, LEXXY_VERSIONS)
        css = tmp_path / "css"

        editor = (css / "lexxy-editor.css").read_bytes()
        assert editor == b"/* lexxy-editor.css */\n" + lexxy.custom_css["lexxy-editor.css"]
        content = (css / "lexxy-content.css").read_bytes()
        assert content.endswith(lexxy.custom_css["lexxy-content.css"])
        assert (css / "lexxy-variables.css").read_text() == "/* lexxy-variables.css */\n"

    def test_a_bundle_without_the_activestorage_import_stops(self, lexxy_cdn, tmp_path):
        (lexxy_cdn / "lexxy-1.2.3.mjs").write_bytes(b"var a=1;export{a};")

        with pytest.raises(SystemExit, match="found 0"):
            vendor.lexxy(tmp_path, LEXXY_VERSIONS)

        assert not (tmp_path / "js").exists()

    def test_an_activestorage_that_imports_other_files_stops(self, lexxy_cdn, tmp_path):
        (lexxy_cdn / "activestorage-4.5.6.mjs").write_bytes(
            b'import a from"/spark-md5@3.0.2";export{a};'
        )

        with pytest.raises(SystemExit, match="imports other files"):
            vendor.lexxy(tmp_path, LEXXY_VERSIONS)

        assert not (tmp_path / "js" / "vendor" / "activestorage.js").exists()

    def test_a_missing_file_is_an_error(self, lexxy_cdn, tmp_path):
        (lexxy_cdn / "helpers-1.2.3.mjs").unlink()

        with pytest.raises(OSError, match="404"):
            vendor.lexxy(tmp_path, LEXXY_VERSIONS)


class TestHotwire:
    @pytest.fixture()
    def hotwire_cdn(self, cdn, monkeypatch):
        folder, url = cdn
        (folder / "stimulus-1.1.1.js").write_text("// stimulus 1.1.1\n")
        (folder / "turbo-2.2.2.js").write_text("// turbo 2.2.2\n")
        packages = {
            "@hotwired/stimulus": {
                "url": url + "/stimulus-{version}.js",
                "filename": "stimulus.js",
            },
            "@hotwired/turbo": {
                "url": url + "/turbo-{version}.js",
                "filename": "turbo.js",
            },
        }
        monkeypatch.setattr(hotwire, "PACKAGES", packages)
        return folder

    def test_writes_the_files(self, hotwire_cdn, tmp_path):
        target = tmp_path / "assets"
        vendor.hotwire(str(target), HOTWIRE_VERSIONS)

        folder = target / "js" / "vendor"
        assert (folder / "stimulus.js").read_text() == "// stimulus 1.1.1\n"
        assert (folder / "turbo.js").read_text() == "// turbo 2.2.2\n"

    def test_a_missing_file_is_an_error(self, hotwire_cdn, tmp_path):
        (hotwire_cdn / "turbo-2.2.2.js").unlink()

        with pytest.raises(OSError, match="404"):
            vendor.hotwire(tmp_path, HOTWIRE_VERSIONS)

    def test_the_files_are_the_ones_in_the_import_map_of_new_apps(self):
        import_map = (
            REPO_ROOT / "blueprint" / "[[app_name]]" / "config" / "import_map.tt.py"
        ).read_text()

        for info in hotwire.PACKAGES.values():
            assert f'"js/vendor/{info["filename"]}"' in import_map


class TestScripts:
    """The `bin/vendor-*.py` scripts: the ones of the repo, and the copies
    that new apps and the rich text addon get."""

    @pytest.mark.parametrize(
        "path",
        [
            REPO_ROOT / "bin" / "vendor-lexxy.py",
            RICH_TEXT_BLUEPRINT / "bin" / "vendor-lexxy.py",
        ],
    )
    def test_lexxy_versions_are_the_vendored_ones(self, path):
        versions = runpy.run_path(str(path))["VERSIONS"]
        vendored = RICH_TEXT_BLUEPRINT / "assets" / "js" / "vendor"

        for name, filename in (
            ("@37signals/lexxy", "lexxy.js"),
            ("@rails/activestorage", "activestorage.js"),
        ):
            header = (vendored / filename).read_text().split("\n", 1)[0]
            assert header == f"/* esm.sh - {name}@{versions[name]} */"

    def test_hotwire_versions_are_the_same_in_new_apps(self):
        ours = runpy.run_path(str(REPO_ROOT / "bin" / "vendor-hotwire.py"))
        theirs = runpy.run_path(str(REPO_ROOT / "blueprint" / "bin" / "vendor-hotwire.py"))

        assert ours["VERSIONS"] == theirs["VERSIONS"]
        assert set(ours["VERSIONS"]) == set(hotwire.PACKAGES)

    def test_the_targets(self):
        ours = runpy.run_path(str(REPO_ROOT / "bin" / "vendor-lexxy.py"))
        assert ours["TARGET"] == RICH_TEXT_BLUEPRINT / "assets"

        ours = runpy.run_path(str(REPO_ROOT / "bin" / "vendor-hotwire.py"))
        assert ours["TARGET"] == REPO_ROOT / "blueprint" / "assets"

        theirs = runpy.run_path(str(RICH_TEXT_BLUEPRINT / "bin" / "vendor-lexxy.py"))
        assert theirs["TARGET"] == RICH_TEXT_BLUEPRINT / "assets"
