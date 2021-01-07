import os
import re

from whitenoise.compress import Compressor

from blog.app import static_path


WEBPACK = "./node_modules/.bin/webpack"
POSTCSS = (
    "./node_modules/.bin/postcss ./src/css/*.css"
    " --base src --dir public"
)
root_path = str(static_path.parent)


def _run(cmd):
    print(cmd)
    os.system(cmd)


def _remove_compressed_from(name):
    for path in [path for glob in [f"{name}/*.br", f"{name}/*.gz"] for path in static_path.rglob(glob)]:
        os.remove(path)


def wcss():
    """Build the CSS bundles and keep monitoring the CSS files for changes."""
    os.chdir(root_path)
    _remove_compressed_from("css")
    _run(
        "./node_modules/.bin/postcss"
        " ./src/css/**/*.css"
        " --base src --dir public --watch"
    )


def wjs():
    """Build the JS bundles and keep monitoring the CSS files for changes."""
    os.chdir(root_path)
    _remove_compressed_from("js")
    _run(f"{WEBPACK} --watch")


def build():
    """Builds all bundles, deleting first, the old ones.
    """
    css()
    js()


def css():
    """Build the CSS bundles."""
    os.chdir(root_path)
    _remove_compressed_from("css")
    print("\n********** Updating css bundles **********")
    _run(POSTCSS)


def js():
    """Build the JS bundles."""
    os.chdir(root_path)
    _remove_compressed_from("js")
    print("\n********** Updating js bundles **********")
    _run(WEBPACK)
    print()


def clean():
    """Delete all compressed assets.
    """
    for path in [
        path
        for glob in ["**/*.br", "**/*.gz"]
        for path in static_path.rglob(glob)
    ]:
        os.remove(path)


def buildp():
    """Builds all bundles for production and generate compressed versions.
    """
    print("\n********** Updating bundles **********")
    os.environ["NODE_ENV"] = "production"
    os.chdir(root_path)
    _run(f"{WEBPACK} --mode production")
    _run(POSTCSS)

    print("\n********** Compressing **********")
    compress()

    print("\n********** Done. **********")



skip_extensions = [
    "jpg", "jpeg", "png", "gif", "webp",
    "zip", "gz", "tgz", "bz2", "tbz", "xz", "br",
    "swf", "flv",
    "woff", "woff2",
]
skip_compress = (
    r"^[\.\_]",
    r"\.({0})$".format("|".join(map(re.escape, skip_extensions))),
)
skip = [re.compile(rx, re.IGNORECASE) for rx in skip_compress]


def should_compress(filename):
    for rxc in skip:
        if rxc.search(filename):
            return False
    return True


def compress():
    compressor = Compressor(use_gzip=True, use_brotli=True, quiet=False)
    for dirpath, _, files in os.walk(static_path):
        for filename in files:
            if should_compress(filename):
                path = os.path.join(dirpath, filename)
                for compressed in compressor.compress(path):  # noqa
                    pass
