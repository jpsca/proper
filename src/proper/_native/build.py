"""Compiles Proper's native code with Free Pascal (3.2.2 or later):
`libproper_native.so`, and `minijx`, the compiler of the views (from
`views/`: a program of its own, run once when the app starts, see
`proper.views`).

    uv run python src/proper/_native/build.py   # next to this file, for this machine
    make native                                 # the same

A script, not `-m proper._native.build`: importing `proper` loads the
library, which isn't there yet.

`PROPER_FPC` names another compiler, for example a cross compiler for
ARM64; both are built for the CPU that compiler targets.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).parent


def build(out: Path = HERE / "libproper_native.so", fpc: str | None = None) -> Path:
    """Compile the library to `out` and return its path."""
    fpc = fpc or os.environ.get("PROPER_FPC") or shutil.which("fpc")
    if not fpc:
        raise RuntimeError("building Proper's native code needs Free Pascal (fpc)")
    with tempfile.TemporaryDirectory() as units:
        result = subprocess.run(
            [
                fpc,
                "-Mobjfpc",
                "-O2",
                "-fPIC",
                "-vew",
                f"-Fu{HERE}",
                f"-Fu{HERE / 'sha256'}",
                f"-Fi{HERE / 'sha256'}",
                f"-Fi{HERE}",
                f"-FU{units}",
                f"-o{out}",
                str(HERE / "proper_native.pas"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    # what fpc says (each unit, the linking, the warnings), success or not
    print(result.stdout, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"fpc could not compile Proper's native code:\n{result.stdout}")
    return out


def build_views_compiler(out: Path = HERE / "minijx", fpc: str | None = None) -> Path:
    """Compile the views compiler to `out` and return its path. It is a
    static executable: it links no library."""
    fpc = fpc or os.environ.get("PROPER_FPC") or shutil.which("fpc")
    if not fpc:
        raise RuntimeError("building Proper's native code needs Free Pascal (fpc)")
    views = HERE / "views"
    with tempfile.TemporaryDirectory() as units:
        result = subprocess.run(
            [
                fpc,
                f"@{views / 'minijx.cfg'}",
                f"-Fu{views}",
                f"-FU{units}",
                f"-o{out}",
                str(views / "minijx.lpr"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            # `minijx --version` says this; the runtime checks the format only
            env={**os.environ, "MINIJX_VERSION": "proper"},
        )
    print(result.stdout, end="", file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"fpc could not compile the views compiler:\n{result.stdout}")
    return out


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    print(build(out / "libproper_native.so"))
    print(build_views_compiler(out / "minijx"))
