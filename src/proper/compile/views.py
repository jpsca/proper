"""The views as Python modules, compiled by minijx.

`compile_views` is what `lower` does when the app starts: compile every view
of the app's catalog into `COMPILED_PATH`. The compiler writes each module
atomically, so the workers of a server can all do it at the same time.

Outside of debug mode, the views that are already compiled are used as they
are. That is how an app whose views were compiled when it was built, with
`proper jx compile`, starts without writing anything.
"""
import typing as t
from pathlib import Path

from minijx.catalog import module_path, output_names

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


def views_are_compiled(app: "App") -> bool:
    """Whether every view of the app's catalog has a compiled module that is
    not older than it.

    This only compares the modification times of the files. A module can
    still be out of date for another reason, like a view it imports that
    changed or other custom tags: minijx checks that the first time it loads
    the module, and compiles it again."""
    catalog = app.catalog
    assert catalog.output is not None
    for folder, name in zip(catalog.folders, output_names(catalog.folders), strict=True):
        for jx in folder.rglob("*.jx"):
            py = module_path(catalog.output / name / jx.relative_to(folder))
            try:
                if py.stat().st_mtime_ns < jx.stat().st_mtime_ns:
                    return False
            except FileNotFoundError:
                return False
    return True


def compile_views(app: "App", *, force: bool = False) -> bool:
    """Compile every view of the app's catalog. Returns whether it did.
    Raises `minijx.CompileError` listing every error.

    It returns `False`, and the compiled modules are used as they are:

    - When there is no minijx compiler for this platform.
    - Outside of debug mode, when every view is already compiled (see
      `views_are_compiled`), unless `force` is true. In debug mode the views
      are always compiled, so the errors of all of them are reported.
    """
    if not app.catalog.compiler:
        logger.info("No minijx compiler: using the compiled views in %s", app.catalog.output)
        return False
    if not force and not app.config.DEBUG and views_are_compiled(app):
        logger.info("Using the compiled views in %s", app.catalog.output)
        return False
    app.catalog.compile()
    return True
