"""Verify that bundled templates are actually included when the package is built.

These are *data* files (Jx scaffolds and core templates) that the framework reads
at runtime, so a `package-data` glob typo would silently ship a broken Proper
without any unit test noticing. We build a real wheel and inspect its contents.
"""
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
SRC = PROJECT_ROOT / "src"


def _expected_members() -> list[str]:
    """Template files that must end up inside the wheel, as wheel-relative paths.

    Wheel members are stored relative to `src/` (e.g. `proper/core/templates/...`),
    which is exactly what `relative_to(SRC)` produces.
    """
    expected: set[str] = set()

    # Resource/addon scaffolds read at runtime by the `proper` CLI generators.
    for path in (SRC / "proper" / "_blueprints").rglob("*"):
        if path.is_file() and "views" in path.relative_to(SRC).parts:
            expected.add(path.relative_to(SRC).as_posix())

    # Core framework templates (error pages, debug views, default index...).
    for path in (SRC / "proper" / "core" / "templates").iterdir():
        if path.is_file():
            expected.add(path.relative_to(SRC).as_posix())

    return sorted(expected)


@pytest.fixture(scope="module")
def wheel_members(tmp_path_factory) -> set[str]:
    if shutil.which("uv") is None:
        pytest.skip("uv is required to build the wheel")

    # Build from a clean copy of the source. A stale `build/` or `*.egg-info` in
    # the working tree leaks files into the artifact (setuptools assembles from
    # `build/lib` and reuses `SOURCES.txt`), which would mask a broken
    # `package-data` glob and let this test pass for the wrong reason.
    project_copy = tmp_path_factory.mktemp("proper_src")
    for name in ("pyproject.toml", "README.md", "MIT-LICENSE"):
        shutil.copy(PROJECT_ROOT / name, project_copy / name)
    shutil.copytree(
        SRC,
        project_copy / "src",
        ignore=shutil.ignore_patterns("*.egg-info", "__pycache__", "*.pyc", "*.pyo"),
    )

    out_dir = project_copy / "_wheel"
    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir), str(project_copy)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"uv build failed:\n{result.stdout}\n{result.stderr}"

    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"

    with zipfile.ZipFile(wheels[0]) as zf:
        return set(zf.namelist())


def test_expected_template_set_is_discovered():
    # Guard against the discovery globs silently matching nothing, which would
    # make `test_templates_are_packed` pass for the wrong reason.
    expected = _expected_members()
    assert any("/views/" in member for member in expected)
    assert any("core/templates/" in member for member in expected)


def test_templates_are_packed(wheel_members):
    missing = [m for m in _expected_members() if m not in wheel_members]
    assert not missing, "Templates missing from built wheel:\n" + "\n".join(missing)
