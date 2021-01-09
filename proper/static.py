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


def compile(app_root):
    digest(app_root)
    print()
    compress(app_root)


def digest(app_root):
    echo("<b>-- Hashing files --</b>")
    manifest = {}
    root = app_root.parent / STATIC_FOLDER
    digestor = Digestor()

    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_digest(filename):
                path = Path(dirpath) / filename
                new_path = digestor.digest(path).relative_to(root)
                manifest[str(path.relative_to(root))] = str(new_path)
                print(new_path)

    manifest_json = json.dumps(manifest)
    (app_root.parent / STATIC_MANIFEST).write_text(manifest_json)


def compress(app_root):
    echo("<b>-- Compressing files --</b>")
    root = app_root.parent / STATIC_FOLDER
    compressor = Compressor(use_gzip=True, use_brotli=bool(brotli), quiet=False)
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _should_compress(filename):
                path = os.path.join(dirpath, filename)
                for comp in compressor.compress(path):
                    pass  # Whitenoise is weird like this


def clean(app_root):
    """Delete all compressed assets."""
    echo("<b>-- Removing files --</b>")
    root = app_root.parent / STATIC_FOLDER
    for dirpath, _, files in os.walk(root):
        for filename in files:
            if _is_compressed(filename) or _is_inmutable(filename):
                path = (Path(dirpath) / filename)
                print(path)
                path.unlink()


UNDIGESTABLE = (".map", )
RE_SKIP_DIGEST = (
    r"^[\.\_]",
    r"\.({0})$".format("|".join(map(re.escape, UNDIGESTABLE))),
)
SKIP_DIGEST = [re.compile(rx, re.IGNORECASE) for rx in RE_SKIP_DIGEST]

COMPRESSED = (".gz", ".br")
UNCOMPRESSABLE = (
    ".map", "jpg", "jpeg", "png", "gif", "webp",
    "zip", "gz", "tgz", "bz2", "tbz", "xz", "br",
    "swf", "flv",
    "woff", "woff2",
)
RE_SKIP_COMPRESS = (
    r"^[\.\_]",
    r"\.({0})$".format("|".join(map(re.escape, UNCOMPRESSABLE))),
)
SKIP_COMPRESS = [re.compile(rx, re.IGNORECASE) for rx in RE_SKIP_COMPRESS]


def _is_compressed(filename):
    return filename.endswith(COMPRESSED)


def _is_inmutable(filename):
    return bool(RE_INMUTABLES_FILE.match(filename))


def _should_digest(filename):
    if _is_inmutable(filename):
        return False
    for rxc in SKIP_DIGEST:
        if rxc.search(filename):
            return False
    return True


def _should_compress(filename):
    if not _is_inmutable(filename):
        return False
    for rxc in SKIP_COMPRESS:
        if rxc.search(filename):
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



