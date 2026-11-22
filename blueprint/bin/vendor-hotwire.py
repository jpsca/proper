#!/usr/bin/env python3
"""Download pinned Stimulus and Turbo bundles and save them as the
vendored JS files.

Run when bumping the pinned versions:

```bash
uv run python bin/vendor-hotwire.py
```

The output goes to `assets/js/vendor/`
"""
from pathlib import Path

from proper import vendor


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "assets"

VERSIONS = {
    "@hotwired/stimulus": "3.2.2",
    "@hotwired/turbo": "8.0.23",
}

if __name__ == "__main__":
    vendor.hotwire(TARGET, VERSIONS)
