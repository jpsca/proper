#!/usr/bin/env python3
"""Download pinned Stimulus and Turbo bundles and save them as the
vendored JS files shipped with newly-created Proper apps.

Run when bumping the pinned versions:

```bash
uv run python bin/vendor-hotwire.py
# or
make vendor-hotwire
```

The output goes to:

    blueprint/[[app_name]]/assets/js/vendor/

Files are then committed to the Proper repo so newly-created apps
work without a runtime CDN dependency.

The destination filenames (`stimulus.js`, `turbo.js`) match the
default `IMPORT_MAP` entries in
`blueprint/[[app_name]]/config/import_map.tt.py`.
"""
import urllib.request
from pathlib import Path


# Each package gets a (url_template, output_filename) pair. We pull the
# pre-built single-file bundles that Hotwire ships in their npm packages
# directly - these are documented entry points in the Hotwire docs and
# are guaranteed to be self-contained, with no external imports the
# browser would chase back to a CDN.
PACKAGES = {
    "@hotwired/stimulus": {
        "version": "3.2.2",
        "url": "https://unpkg.com/@hotwired/stimulus@{version}/dist/stimulus.js",
        "filename": "stimulus.js",
    },
    "@hotwired/turbo": {
        "version": "8.0.23",
        "url": "https://unpkg.com/@hotwired/turbo@{version}/dist/turbo.es2017-esm.js",
        "filename": "turbo.js",
    },
}

OUTPUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "blueprint" / "[[app_name]]"
    / "assets" / "js" / "vendor"
)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for pkg, info in PACKAGES.items():
        url = info["url"].format(version=info["version"])
        dest = OUTPUT_DIR / info["filename"]
        print(f"  → {pkg}@{info['version']}")
        print(f"    from: {url}")
        print(f"    to:   {dest}")
        with urllib.request.urlopen(url) as response:  # noqa: S310
            content = response.read()
        dest.write_bytes(content)
    print(f"\nWrote {len(PACKAGES)} files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
