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


STATIC_FOLDER = "static/public"
STATIC_MANIFEST = "static/cache_manifest.json"
RX_INMUTABLES_FILE = r"^.+\.[0-9a-f]{12}\..+$"
RE_INMUTABLES_FILE = re.compile(RX_INMUTABLES_FILE)


def compile(app):
    root = app.root_path.parent
    static_root = root / STATIC_FOLDER
    manifest_path = root / STATIC_MANIFEST
    digest(static_root, manifest_path)
    print()
    if app._config.static.compress:
        compress(static_root)


def digest(root, manifest_path):
    echo("<b>-- Hashing files --</b>")
    digestor = Digestor(root)

    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_digest(filename):
                path = Path(dirpath) / filename
                print(digestor.digest(path))

    manifest_json = json.dumps(digestor.manifest)
    manifest_path.write_text(manifest_json)


def compress(root):
    echo("<b>-- Compressing files --</b>")
    compressor = Compressor(use_gzip=True, use_brotli=bool(brotli), quiet=False)
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_compress(filename):
                path = os.path.join(dirpath, filename)
                for comp in compressor.compress(path):
                    pass  # Whitenoise is weird like this


def clean(root):
    echo("<b>-- Removing hashed and/or compressed files --</b>")
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _is_compressed(filename) or _is_inmutable(filename):
                path = (Path(dirpath) / filename)
                print(path.relative_to(root))
                path.unlink()


IGNORE_STARTS = (".", "_")
COMPRESSED_ENDS = (".gz", ".br")
UNDIGESTABLE_ENDS = (".map")
UNCOMPRESSABLE_ENDS = (
    ".map", "jpg", "jpeg", "png", "gif", "webp",
    "zip", "gz", "tgz", "bz2", "tbz", "xz", "br",
    "swf", "flv",
    "woff", "woff2",
)


def _is_compressed(filename):
    return filename.endswith(COMPRESSED_ENDS)


def _is_inmutable(filename):
    return bool(RE_INMUTABLES_FILE.match(filename))


def _should_digest(filename):
    if filename.startswith(IGNORE_STARTS):
        return False
    if _is_inmutable(filename):
        return False
    if filename.endswith(UNDIGESTABLE_ENDS):
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


# WEBPACK = "./node_modules/.bin/webpack"
# POSTCSS = (
#     "./node_modules/.bin/postcss ./src/css/*.css"
#     " --base src --dir public"
# )
# root_path = str(static_path.parent)


# def _run(cmd):
#     print(cmd)
#     os.system(cmd)



# def wcss():
#     """Build the CSS bundles and keep monitoring the CSS files for changes."""
#     os.chdir(root_path)
#     _run(
#         "./node_modules/.bin/postcss"
#         " ./src/css/**/*.css"
#         " --base src --dir public --watch"
#     )


# def wjs():
#     """Build the JS bundles and keep monitoring the CSS files for changes."""
#     os.chdir(root_path)
#     _run(f"{WEBPACK} --watch")


# def build():
#     """Builds all bundles, deleting first, the old ones.
#     """
#     css()
#     js()


# def css():
#     """Build the CSS bundles."""
#     os.chdir(root_path)
#     print("\n********** Updating css bundles **********")
#     _run(POSTCSS)


# def js():
#     """Build the JS bundles."""
#     os.chdir(root_path)
#     print("\n********** Updating js bundles **********")
#     _run(WEBPACK)
#     print()


# def buildp():
#     """Builds all bundles for production and generate compressed versions.
#     """
#     print("\n********** Updating bundles **********")
#     os.environ["NODE_ENV"] = "production"
#     os.chdir(root_path)
#     _run(f"{WEBPACK} --mode production")
#     _run(POSTCSS)

#     print("\n********** Compressing **********")
#     compress()

#     print("\n********** Done. **********")



