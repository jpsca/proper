"""
Proper's views: Jx components compiled to Python functions by minijx.

This is minijx (github.com/jpsca/minijx, at 0.1.0), vendored into Proper:
the runtime here, the compiler in `proper/_native/views/` (Free Pascal),
built with Proper's native code as `proper/_native/minijx`. The code the
compiler generates imports `proper.views.runtime`, `proper.views.filters`
and `proper.views.tests`.
"""

# What `minijx --version` of Proper's compiler says (`build.py`)
__version__ = "proper"

from .attrs import Attrs  # noqa: E402
from .catalog import (  # noqa: E402
    Catalog,
    CompileError,
    Component,
    ComponentNotCompiledError,
    ComponentNotFoundError,
)
from .loop import Loop  # noqa: E402
from .runtime import (  # noqa: E402
    InvalidPropType,
    concat,
    escape,
    getattr_,
    getitem,
    has_attr,
)


__all__ = [
    "Catalog", "Component", "ComponentNotCompiledError", "ComponentNotFoundError", "CompileError",
    "Attrs", "InvalidPropType", "Loop", "concat", "escape", "getattr_", "getitem", "has_attr"]
