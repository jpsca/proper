#!/usr/bin/env python3
"""Check that each wheel is tagged `manylinux_2_34_<cpu>` and that auditwheel
agrees: that `libproper_native.so` needs nothing newer than glibc 2.34 and no
library outside the manylinux policy.

`hatch_build.py` tags a wheel with the newest glibc symbol its library
needs. A runner with a newer glibc could raise that tag without anyone
noticing, and the wheel would no longer install on older distributions;
this check fails then.

```bash
uv run python bin/check-wheels.py dist/*.whl
```

Needs `uvx` (auditwheel runs through it).
"""
import re
import subprocess
import sys
from pathlib import Path


EXPECTED = "manylinux_2_34"


def check(wheel: Path) -> str | None:
    """`None` when the wheel is right, else what is wrong."""
    tag = wheel.stem.rsplit("-", 1)[-1]
    if not re.fullmatch(rf"{EXPECTED}_(x86_64|aarch64)", tag):
        return f"tagged {tag}, not {EXPECTED}_<cpu>"
    result = subprocess.run(
        ["uvx", "auditwheel", "show", str(wheel)], capture_output=True, text=True
    )
    report = " ".join(result.stdout.split())
    if result.returncode != 0:
        return f"auditwheel failed:\n{result.stdout}{result.stderr}"
    if f'consistent with the following platform tag: "{tag}"' not in report:
        return f"auditwheel does not agree with {tag}:\n{result.stdout}"
    return None


def main(wheels: list[str]) -> int:
    if not wheels:
        print("usage: check-wheels.py WHEEL...", file=sys.stderr)
        return 2
    failed = 0
    for name in wheels:
        problem = check(Path(name))
        if problem:
            failed += 1
            print(f"FAIL {name}: {problem}", file=sys.stderr)
        else:
            print(f"ok   {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
