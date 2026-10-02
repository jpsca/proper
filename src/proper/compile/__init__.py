"""Decisions that cannot change between requests, taken once.

See `PLAN_COMPILE.md` at the root of the repository. Each module is one
lowering pass; `lower` runs them all for an app.
"""
import typing as t

from minijx import CompileError

from ..helpers import logger
from .dispatch import (  # noqa
    DispatchPlan,
    LoweringError,
    plan_for,
    resolve_view,
)
from .dispatch import lower as lower_dispatch
from .routes import RouteTable, lower_routes  # noqa
from .views import compile_views, compiled_views_path, views_are_compiled  # noqa


if t.TYPE_CHECKING:
    from ..app import App


def lower(app: "App", *, strict: bool = True) -> list[DispatchPlan]:
    """Lower every routed action of `app` (validating its callbacks) and its
    router, then compile every view. Raises `LoweringError` on the first
    invalid controller, and `minijx.CompileError` listing every invalid view.

    With `strict=False` (debug mode, where a view is being edited) the views
    that compile are written anyway and the errors are only logged: each
    shows when its view is rendered, and the server still starts."""
    plans = lower_dispatch(app)
    app.router.lower()
    try:
        compile_views(app)
    except CompileError as err:
        if strict:
            raise
        logger.error("Some views do not compile:\n%s", err)
    return plans


install = lower
