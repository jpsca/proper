"""Compiles Proper's native code (`src/proper/_native/`) with Free Pascal.

An editable install gets `libproper_native.so` and `jxc` (the compiler
of the views) next to the package's modules, for this machine. A wheel gets it from `build/native-<cpu>/`, so a
wheel for another CPU leaves the editable install alone: `PROPER_FPC`
names the compiler, for example an ARM64 cross compiler, and the wheel is
tagged for the CPU that compiler targets (`fpc -iTP`) and for the newest
glibc symbol version the library needs (`objdump -T`).

    PROPER_FPC=/path/to/fpc-aarch64 uv build --wheel

`make native` compiles it again after a change to the Pascal sources: an
editable install doesn't.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


# fpc -iTP -> the wheel's platform tag
CPUS = {
    "x86_64": "x86_64",
    "aarch64": "aarch64",
}


def manylinux(library: Path) -> str:
    """The manylinux tag for `library`: the newest glibc symbol version it
    needs, which is the oldest glibc that loads it."""
    objdump = shutil.which("objdump")
    if not objdump:
        raise RuntimeError("tagging the Proper wheel needs objdump (binutils)")
    symbols = subprocess.run(
        [objdump, "-T", str(library)], check=True, capture_output=True, text=True
    ).stdout
    versions = {
        tuple(int(n) for n in v.split("."))
        for v in re.findall(r"\bGLIBC_(\d+(?:\.\d+)+)\b", symbols)
    }
    if not versions:
        raise RuntimeError(f"no glibc symbol in {library}: is it linked against glibc?")
    major, minor = max(versions)[:2]
    return f"manylinux_{major}_{minor}"


def load_build(root: Path):
    """`src/proper/_native/build.py`, loaded by path: importing `proper` would
    load the library this builds."""
    spec = importlib.util.spec_from_file_location(
        "proper_native_build", root / "src" / "proper" / "_native" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        if not sys.platform.startswith("linux"):
            raise RuntimeError("Proper runs only on Linux")

        fpc = os.environ.get("PROPER_FPC") or shutil.which("fpc")
        if not fpc:
            raise RuntimeError("building Proper needs Free Pascal >= 3.2.2 (fpc)")
        fpc = str(Path(fpc).resolve()) if os.sep in fpc else fpc
        cpu = subprocess.run(
            [fpc, "-iTP"], check=True, capture_output=True, text=True
        ).stdout.strip()
        if cpu not in CPUS:
            raise RuntimeError(f"Proper builds for {', '.join(CPUS)}, not {cpu}")

        root = Path(self.root)
        build = load_build(root)
        if version == "editable":
            out = root / "src" / "proper" / "_native"  # imported from here
        else:
            out = root / "build" / f"native-{cpu}"
            out.mkdir(parents=True, exist_ok=True)
        library = build.build(out / "libproper_native.so", fpc=fpc)
        compiler = build.build_views_compiler(out / "jxc", fpc=fpc)

        if version != "editable":
            build_data["force_include"][str(library)] = "proper/_native/libproper_native.so"
            build_data["force_include"][str(compiler)] = "proper/_native/jxc"
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{manylinux(library)}_{CPUS[cpu]}"
