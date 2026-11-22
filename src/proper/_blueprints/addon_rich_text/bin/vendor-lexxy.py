#!/usr/bin/env python3
"""Download a pinned Lexxy bundle (JS + CSS) and save it to the
vendored JS/CSS directories.

Run when bumping the pinned version:

```bash
uv run python bin/vendor-lexxy.py
```

The output goes to `assets/js/vendor/` and `assets/css/`.
"""
from pathlib import Path

from proper import vendor


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "assets"

VERSIONS = {
    "@37signals/lexxy": "1.0.4",
    "@rails/activestorage": "8.1.401",
}

if __name__ == "__main__":
    vendor.lexxy(TARGET, VERSIONS)
