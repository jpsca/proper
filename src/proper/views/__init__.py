"""
Proper's views: Jx components compiled to Python functions.

The compiler, jxc, is Free Pascal (`proper/_native/views/`), built with
Proper's native code as `proper/_native/jxc`; this package is the runtime
the modules it generates import (`proper.views.runtime`, `.filters`,
`.tests`), and the catalog that compiles and loads them.
"""

# What `jxc --version` says (`_native/build.py`)
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
