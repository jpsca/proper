#!/usr/bin/env python3
"""Download a pinned Lexxy bundle (JS + CSS) and save it to the
vendored JS/CSS directories shipped with newly-created Proper apps.

Run when bumping the pinned version:

```bash
uv run python bin/vendor-lexxy.py
# or
make vendor-lexxy
```

The JS output is the *bundled* ESM build from esm.sh — a single
self-contained file with all peer dependencies (lexical, dompurify,
@rails/activestorage) inlined. That avoids having to vendor and
import-map each peer individually, which would otherwise be ~10
files for Lexical alone.

Destinations (mirrored to both the general app blueprint and the
rich_text addon blueprint):

    blueprint/[[app_name]]/assets/js/vendor/lexxy.js
    blueprint/[[app_name]]/assets/styles/vendor/lexxy.css
"""
import re
import urllib.request
from pathlib import Path


VERSION = "0.9.12-beta"

JS_URL = f"https://esm.sh/@37signals/lexxy@{VERSION}/es2022/lexxy.bundle.mjs"
HELPERS_URL = f"https://esm.sh/@37signals/lexxy@{VERSION}/es2022/helpers.mjs"
# The four upstream files we inline into one self-contained `lexxy.css`.
# Order matters: variables first (they're referenced by the others).
CSS_SOURCES = (
    "lexxy-variables.css",
    "lexxy-content.css",
    "lexxy-editor.css",
)
CSS_BASE = f"https://unpkg.com/@37signals/lexxy@{VERSION}/dist/stylesheets"

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    REPO_ROOT / "blueprint" / "[[app_name]]" / "assets",
    REPO_ROOT / "src" / "proper" / "blueprints" / "rich_text" / "[[app_name]]" / "assets",
]

custom_css = {
  "lexxy-editor.css": """
:where(lexxy-toolbar) {
    font-size: 0.9em;
}
""",
}


def _download(url: str) -> bytes:
    print(f"    from: {url}")
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read()


def _write_to_targets(rel_path: str, content: bytes) -> None:
    for assets_root in TARGETS:
        dest = assets_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        print(f"    to:   {dest}")


def _rewrite_paths_to_esm_sh(js_bytes: bytes) -> bytes:
    """Rewrite absolute paths in the Lexxy bundle to point at esm.sh.

    esm.sh's `lexxy.bundle.mjs` keeps `import` statements referring to
    paths like `/lexical@^0.44.0/Lexical.prod?target=es2022` — relative
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


def _strip_source_map_reference(js_bytes: bytes) -> bytes:
    """The source map reference comment at the end of the bundle is not
    relevant to us and just adds noise, so we strip it out."""
    return re.sub(rb"^//# sourceMappingURL=.*$", b"", js_bytes, flags=re.MULTILINE)


def main() -> None:
    print(f"  → @37signals/lexxy@{VERSION} (JS bundle)")
    js_content = _download(JS_URL)
    js_content = _rewrite_paths_to_esm_sh(js_content)
    js_content = _strip_source_map_reference(js_content)
    _write_to_targets("js/vendor/lexxy.js", js_content)

    print(f"  → @37signals/lexxy@{VERSION} (helpers)")
    helpers_content = _download(HELPERS_URL)
    helpers_content = _rewrite_paths_to_esm_sh(helpers_content)
    helpers_content = _strip_source_map_reference(helpers_content)
    _write_to_targets("js/vendor/lexxy-helpers.js", helpers_content)

    # Lexxy ships its CSS as four files connected by `@import url("...")`.
    # Proper fingerprints asset filenames, so those relative `@import`s
    # would 404. We download each piece, strip the `@import` lines, and
    # concatenate them into one self-contained `lexxy.css`.
    print(f"  → @37signals/lexxy@{VERSION} (CSS, inlined)")
    parts: list[str] = [f"/* @37signals/lexxy@{VERSION} — inlined stylesheets */"]
    for name in CSS_SOURCES:
        url = f"{CSS_BASE}/{name}"
        css = _download(url).decode("utf-8")
        css = re.sub(r"\s*@import\s+url\([^)]+\);\s*$", "", css, flags=re.MULTILINE)
        if name in custom_css:
            css += "\n\n" + custom_css[name].strip() + "\n"
        parts.append(f"/* --- {name} --- */\n{css.strip()}")

    inlined = ("\n\n".join(parts) + "\n").encode("utf-8")
    _write_to_targets("styles/vendor/lexxy.css", inlined)

    print(f"\nVendored Lexxy {VERSION} into {len(TARGETS)} blueprint(s).")


if __name__ == "__main__":
    main()
