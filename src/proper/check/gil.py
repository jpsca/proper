import os
import re
import subprocess
import sys
import sysconfig
import typing as t
from pathlib import Path

from .problem import ERROR, WARNING, Problem


if t.TYPE_CHECKING:
    from ..app import App


__all__ = ("check_gil", "free_threaded", "gil_enabled", "modules_that_enable_the_gil")

# What Python warns when an extension module turns the GIL back on
RX_GIL_WARNING = re.compile(r"GIL\) has been enabled to load module '([^']+)'")
# Seconds that importing the app again may take
IMPORT_TIMEOUT = 120


def free_threaded() -> bool:
    """Whether this Python was built without the GIL (a "3.14t" build)."""
    return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))


def gil_enabled() -> bool:
    """Whether the GIL is on right now. A free-threaded build turns it back
    on when it imports an extension module that has not declared itself
    safe without it."""
    return getattr(sys, "_is_gil_enabled", lambda: True)()


def check_gil(app: "App") -> list[Problem]:
    """The app runs without the GIL, as `proper run` requires (unless
    `ALLOW_GIL`), and if an extension module turns it on, which one."""
    if not gil_enabled():
        return []
    if app.config.ALLOW_GIL:
        return [Problem(WARNING, "the app runs with the GIL (ALLOW_GIL): more memory, less parallelism")]
    if not free_threaded():
        return [Problem(
            ERROR,
            "this Python has the GIL, so `proper run` refuses to start: install a "
            "free-threaded one with `uv python install 3.14t` (or set ALLOW_GIL = True)",
        )]
    modules = modules_that_enable_the_gil(app.import_name.split(".")[0])
    if not modules:
        return [Problem(
            ERROR,
            "the GIL is on (is PYTHON_GIL=1 set?), so `proper run` refuses to start",
        )]
    names = ", ".join(f"`{name}`" for name in modules)
    return [Problem(
        ERROR,
        f"importing the app turns the GIL back on, so `proper run` refuses to "
        f"start: {names} not declared safe without it. Upgrade or replace it "
        f"(or set ALLOW_GIL = True)",
    )]


def modules_that_enable_the_gil(package: str) -> list[str]:
    """The extension modules that turn the GIL on when `package` is imported,
    in a new process: in this one they are already imported, and Python
    warns only the first time."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHON_GIL"}
    result = subprocess.run(
        [sys.executable, "-W", "always::RuntimeWarning", "-c", f"import {package}"],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=env,
        timeout=IMPORT_TIMEOUT,
    )
    return list(dict.fromkeys(RX_GIL_WARNING.findall(result.stderr)))
