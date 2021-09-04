import json
import os
import re
from pathlib import Path

try:
    import brotli
except ImportError:
    botli = None
from pyceo import echo
from whitenoise.compress import Compressor

from proper.helpers import Digestor


BUNDLE = "npm run bundle"
BUNDLE_PROD = "npm run build"

RX_INMUTABLES_FILE = r"^.+\.[0-9a-f]{12}\..+$"
RE_INMUTABLES_FILE = re.compile(RX_INMUTABLES_FILE)

IGNORE_STARTS = (".", "_")
COMPRESSED_ENDS = (".gz", ".br")
UNCOMPRESSABLE_ENDS = (
    ".map", "jpg", "jpeg", "png", "gif", "webp",
    "zip", "gz", "tgz", "bz2", "tbz", "xz", "br",
    "swf", "flv",
    "woff", "woff2",
)
REPLACEABLE_ENDS = (".css", "js", ".html", ".json", ".xml", ".svg")


def bundle(app):
    """Calls `npm run bundle` in the `static/` folder for building the CSS and JS bundles.
    """
    os.chdir(app.static_path)
    cmd = BUNDLE
    print(cmd)
    os.system(cmd)


def build(app):
    """Calls `npm run build` in the `static/` folder for making production bundles.
    """
    os.chdir(app.static_path)
    cmd = BUNDLE_PROD
    print(cmd)
    os.system(cmd)


def clean(app):
    """Delete all digested and/or compressed assets in static/public.
    """
    public = app.public_path
    echo("<bold>-- Removing hashed and/or compressed files --</>")
    for dirpath, _, files in os.walk(public):
        for filename in files:
            if _is_compressed(filename) or _is_inmutable(filename):
                path = (Path(dirpath) / filename)
                print(path.relative_to(public))
                path.unlink()


def compile(app):
    """Digest and compress the assets in static/public.
    """
    public = app.public_path
    _digest(public, app.static_manifest_path)
    print()
    if app._config.static.compress:
        compress(public)


def _digest(root, manifest_path):
    echo("<bold>-- Hashing files --</>")
    digestor = Digestor(root)

    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_digest(filename):
                path = Path(dirpath) / filename
                print(digestor.digest(path))

    manifest_json = json.dumps(digestor.manifest)
    manifest_path.write_text(manifest_json)

    _replace_urls(root, digestor.manifest)


def _replace_urls(root, manifest):
    """Replace the references to the digested assets with hashed ones
    in CSS and JS files.

    With assets in subfolders, this only works if the full URL relative to the
    `static/` folder is used, eg: `/static/images/bg.png` or `../fonts/museo.woff`.

    An exception to this rule is taken for source maps.
    """
    for filename in manifest.values():
        if not filename.endswith(REPLACEABLE_ENDS):
            continue
        path = root / filename
        text = path.read_text()
        is_js = filename.endswith(".js")

        for name, replacement in manifest.items():
            if is_js and name.endswith(".js.map"):
                name = f"sourceMappingURL={name.rsplit('/')[-1]}"
                replacement = f"sourceMappingURL={replacement.rsplit('/')[-1]}"

            text = text.replace(name, replacement)
        path.write_text(text)


def compress(root):
    echo("<bold>-- Compressing files --</bold>")
    compressor = Compressor(use_gzip=True, use_brotli=bool(brotli), quiet=False)
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_compress(filename):
                path = os.path.join(dirpath, filename)
                for _ in compressor.compress(path):
                    pass  # Whitenoise is weird like this


def _is_compressed(filename):
    return filename.endswith(COMPRESSED_ENDS)


def _is_inmutable(filename):
    return bool(RE_INMUTABLES_FILE.match(filename))


def _should_digest(filename):
    if filename.startswith(IGNORE_STARTS):
        return False
    if _is_inmutable(filename):
        return False
    return True


def _should_compress(filename):
    if filename.startswith(IGNORE_STARTS):
        return False
    if not _is_inmutable(filename):
        return False
    if filename.endswith(UNCOMPRESSABLE_ENDS):
        return False
    return True
