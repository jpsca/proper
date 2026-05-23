# Vendored JS bundles

This directory holds pinned ESM bundles of JS files used by Proper apps.

- Hotwire (Stimulus + Turbo)
- TipTap (core + StarterKit + Link)

**Do not edit these files by hand.**

## How to (re)generate

Run from the Proper repo root:

```sh
make vendor-hotwire
make vendor-tiptap
# or
uv run python bin/vendor-hotwire.py
uv run python bin/vendor-tiptap.py
```

To bump versions, edit `VERSIONS` in the `bin/vendor-*.py` file and re-run.

## Why vendored

- Avoids a runtime CDN dependency (apps work offline / behind firewalls).
- Lets us upgrade on our own cadence — a library breaking change won't
  affect Proper apps until we re-vendor.
- Lets a user replace these files with their own builds if they prefer.
