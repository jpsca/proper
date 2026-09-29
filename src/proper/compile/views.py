"""The views as Python modules, compiled by minijx.

`compile_views` is what `lower` does when the app starts outside of debug
mode: compile every view of the app's catalog into `COMPILED_PATH`. The
compiler writes each module atomically, so the workers of a server can all
do it at the same time.
"""
import typing as t
from pathlib import Path

from minijx.catalog import output_names

from ..helpers import logger


if t.TYPE_CHECKING:
    from ..app import App


def compiled_views_path(app: "App") -> Path:
    """Where the modules of the app's views go: `COMPILED_PATH/views`, with
    `COMPILED_PATH` relative to the folder that holds the app package."""
    catalog = app.catalog
    assert catalog.output is not None
    views = app.views_path.resolve()
    if views not in catalog.folders:
        return catalog.output / views.name
    return catalog.output / output_names(catalog.folders)[catalog.folders.index(views)]


def compile_views(app: "App") -> bool:
    """Compile every view of the app's catalog. Returns whether it did:
    `False` when there is no minijx compiler for this platform, and the
    modules compiled elsewhere are used as they are. Raises
    `minijx.CompileError` listing every error."""
    if not app.catalog.compiler:
        logger.info("No minijx compiler: using the compiled views in %s", app.catalog.output)
        return False
    app.catalog.compile()
    return True
