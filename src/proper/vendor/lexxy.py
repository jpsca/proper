#!/usr/bin/env python3
"""Download a pinned Lexxy bundle (JS + CSS) and save it to the
vendored JS/CSS directories.

Run when bumping the pinned version:

```bash
uv run python bin/vendor-lexxy.py
```

The JS output is the *bundled* ESM build from esm.sh - a single
file with the peer dependencies (lexical, dompurify) inlined. That
avoids having to vendor and import-map each peer individually, which
would otherwise be ~10 files for Lexical alone.

The bundle leaves out `@rails/activestorage`, which it imports when a
file is uploaded. It is vendored as its own file, and the import is
rewritten to the bare name `activestorage`, which the addon adds to the
import map of the app.
"""

import re
import urllib.request
from pathlib import Path


JS_URL = "https://esm.sh/@37signals/lexxy@{version}/es2022/lexxy.bundle.mjs"
HELPERS_URL = "https://esm.sh/@37signals/lexxy@{version}/es2022/helpers.mjs"

ACTIVESTORAGE_URL = "https://esm.sh/@rails/activestorage@{version}/es2022/activestorage.mjs"
# The name of the vendored file in the import map of the app.
ACTIVESTORAGE_NAME = b"activestorage"

CSS_SOURCES = (
    "lexxy-variables.css",
    "lexxy-content.css",
    "lexxy-editor.css",
)
CSS_BASE = "https://cdn.jsdelivr.net/npm/@37signals/lexxy@{version}/dist/stylesheets"

custom_css = {
    "lexxy-editor.css": b"""
:where(lexxy-toolbar) {
  font-size: 0.9em;
}
""",
    "lexxy-content.css": b"""
:where(lexxy-editor) .attachment__caption textarea {
  margin: 0;
}
""",
}


def _download(url: str) -> bytes:
    print(f"    from: {url}")
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read()


def _write_to_target(target: Path, rel_path: str, content: bytes) -> None:
    dest = target / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    print(f"    to:   {dest}")


def _rewrite_paths_to_esm_sh(js_bytes: bytes) -> bytes:
    """Rewrite absolute paths in the Lexxy bundle to point at esm.sh.

    esm.sh's `lexxy.bundle.mjs` keeps `import` statements referring to
    paths like `/lexical@^0.44.0/Lexical.prod?target=es2022` - relative
    to esm.sh's origin. Served from our app, those resolve to 404s.

    We rewrite them to absolute `https://esm.sh/...` URLs so the browser
    fetches peer deps directly from esm.sh. This introduces a runtime
    CDN dependency for those deps but avoids the 30+ files we'd need to
    vendor (lexical core + 12 lexical packages + dompurify + helpers,
    each with `.dev` and `.prod` variants).
    """
    # Rewrite quoted absolute paths starting with `/` followed by a
    # package name (`@scope/pkg@` or `pkg@`).
    js = re.sub(rb'"(/(?:@[^/"]+/)?[^/"]+@[^"]+)"', rb'"https://esm.sh\1"', js_bytes)
    # `./helpers.mjs` is Lexxy's sibling file; we vendor it too.
    js = js.replace(b'"./helpers.mjs"', b'"./lexxy-helpers.js"')
    return js


def _import_activestorage_by_name(js_bytes: bytes) -> bytes:
    """Rewrite the import of `@rails/activestorage` in the Lexxy bundle
    to the name the vendored file has in the import map.

    The bundle has it as `import("/@rails/activestorage@>=%207.0.0?...")`,
    a path of esm.sh. With the bare name, the browser loads the file from
    the app itself.
    """
    js, count = re.subn(
        rb'"/@rails/activestorage@[^"]*"', b'"' + ACTIVESTORAGE_NAME + b'"', js_bytes
    )
    if count != 1:
        raise SystemExit(f"Expected one import of @rails/activestorage, found {count}")
    return js


def _strip_source_map_reference(js_bytes: bytes) -> bytes:
    """The source map reference comment at the end of the bundle is not
    relevant to us and just adds noise, so we strip it out."""
    return re.sub(rb"^//# sourceMappingURL=.*$", b"", js_bytes, flags=re.MULTILINE)


def vendor_lexxy(target: Path | str, versions: dict[str, str]) -> None:
    target = Path(target)
    lexxy_version = versions["@37signals/lexxy"]
    activestorage_version = versions["@rails/activestorage"]

    print(f"  → @37signals/lexxy@{lexxy_version} (JS bundle)")
    js_content = _download(JS_URL.format(version=lexxy_version))
    js_content = _import_activestorage_by_name(js_content)
    js_content = _rewrite_paths_to_esm_sh(js_content)
    js_content = _strip_source_map_reference(js_content)
    _write_to_target(target, "js/vendor/lexxy.js", js_content)

    print(f"  → @37signals/lexxy@{lexxy_version} (helpers)")
    helpers_content = _download(HELPERS_URL.format(version=lexxy_version))
    helpers_content = _rewrite_paths_to_esm_sh(helpers_content)
    helpers_content = _strip_source_map_reference(helpers_content)
    _write_to_target(target, "js/vendor/lexxy-helpers.js", helpers_content)

    print(f"  → @rails/activestorage@{activestorage_version}")
    activestorage_content = _download(
        ACTIVESTORAGE_URL.format(version=activestorage_version)
    )
    if re.search(rb'\b(?:from|import)\s*\(?\s*"', activestorage_content):
        raise SystemExit("The @rails/activestorage module imports other files")
    activestorage_content = _strip_source_map_reference(activestorage_content)
    _write_to_target(target, "js/vendor/activestorage.js", activestorage_content)

    print(f"  → @37signals/lexxy@{lexxy_version} (CSS)")
    for name in CSS_SOURCES:
        css_content = _download(f"{CSS_BASE.format(version=lexxy_version)}/{name}")
        if name in custom_css:
            css_content += custom_css[name]
        _write_to_target(target, f"css/{name}", css_content)
