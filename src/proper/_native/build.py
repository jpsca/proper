"""Compiles `libproper_native.so` with Free Pascal (3.2.2 or later).

    uv run python src/proper/_native/build.py   # next to this file, for this machine
    make native                                 # the same

A script, not `-m proper._native.build`: importing `proper` loads the
library, which isn't there yet.

`PROPER_FPC` names another compiler, for example a cross compiler for
ARM64; the library is built for the CPU that compiler targets.
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


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "libproper_native.so"))
