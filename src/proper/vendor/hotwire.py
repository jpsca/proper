#!/usr/bin/env python3
"""Download pinned Stimulus and Turbo bundles and save them as the
vendored JS files.

Run when bumping the pinned versions:

```bash
uv run python bin/vendor-hotwire.py
# or
make vendor-hotwire
```

The destination filenames (`stimulus.js`, `turbo.js`) match the
default `IMPORT_MAP` entries.
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
        "url": "https://unpkg.com/@hotwired/stimulus@{version}/dist/stimulus.js",
        "filename": "stimulus.js",
    },
    "@hotwired/turbo": {
        "url": "https://unpkg.com/@hotwired/turbo@{version}/dist/turbo.es2017-esm.js",
        "filename": "turbo.js",
    },
}


def vendor_hotwire(target: Path | str, versions: dict[str, str]) -> None:
    target = Path(target) / "js" / "vendor"

    target.mkdir(parents=True, exist_ok=True)
    for pkg, info in PACKAGES.items():
        version = versions[pkg]
        url = info["url"].format(version=version)
        dest = target / info["filename"]
        print(f"  → {pkg}@{version}")
        print(f"    from: {url}")
        print(f"    to:   {dest}")
        with urllib.request.urlopen(url) as response:  # noqa: S310
            content = response.read()
        dest.write_bytes(content)
