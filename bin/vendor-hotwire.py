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

    blueprint/assets/js/vendor/

Files are then committed to the Proper repo so newly-created apps
work without a runtime CDN dependency.

The destination filenames (`stimulus.js`, `turbo.js`) match the
default `IMPORT_MAP` entries in
`blueprint/[[app_name]]/config/import_map.tt.py`.
"""
from pathlib import Path

from proper import vendor


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "blueprint" / "assets"

VERSIONS = {
    "@hotwired/stimulus": "3.2.2",
    "@hotwired/turbo": "8.0.23",
}

if __name__ == "__main__":
    vendor.hotwire(TARGET, VERSIONS)
