#!/usr/bin/env python3
"""Download a pinned Lexxy bundle (JS + CSS) and save it to the
vendored JS/CSS directories shipped with newly-created Proper apps.

Run when bumping the pinned version:

```bash
uv run python bin/vendor-lexxy.py
# or
make vendor-lexxy
```

The JS output is the *bundled* ESM build from esm.sh - a single
file with the peer dependencies (lexical, dompurify) inlined. That
avoids having to vendor and import-map each peer individually, which
would otherwise be ~10 files for Lexical alone.

The bundle leaves out `@rails/activestorage`, which it imports when a
file is uploaded. It is vendored as its own file, and the import is
rewritten to the bare name `activestorage`, which the addon adds to the
import map of the app.

The files go to the `assets/` folder of the rich_text addon blueprint:

    src/proper/_blueprints/addon_rich_text/assets/
"""
from pathlib import Path

from proper import vendor


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "src" / "proper" / "_blueprints" / "addon_rich_text" / "assets"

VERSIONS = {
    "@37signals/lexxy": "1.0.4",
    "@rails/activestorage": "8.1.401",
}

if __name__ == "__main__":
    vendor.lexxy(TARGET, VERSIONS)
