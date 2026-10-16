"""
Shared helpers: compile .jx files with the views compiler, render them with
the generated Python, and compare with what Jx renders.

What Jx renders is fixed: `expected.json` has, for each test, what Jx
rendered in it, in order (or the error it raised). It was recorded from
minijx's own suite (github.com/jpsca/minijx 0.1.0, against Jx 0.16) on the
tests that passed, so each value is one minijx matched.
"""

import importlib.util
import json
import re
import subprocess
from pathlib import Path

from proper.views.catalog import bundled_compiler


HERE = Path(__file__).resolve().parent
BIN = bundled_compiler()
# The real templates that build the Jx documentation site
JX_VIEWS = HERE / "fixtures" / "jx_docs_views"
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))


def collapse(html: str) -> str:
    """Whitespace-insensitive: runs collapse, and none is kept between tags."""
    return re.sub(r">\s+<", "><", re.sub(r"\s+", " ", html)).strip()


def run_minijx(*folders: Path) -> subprocess.CompletedProcess:
    assert BIN is not None, "build the compiler first: make native"
    return subprocess.run([str(BIN), *map(str, folders)], capture_output=True, text=True)


def load_module(py_path: Path):
    spec = importlib.util.spec_from_file_location(f"gen_{py_path.stem}_{id(py_path)}", py_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class JxError(Exception):
    """An error Jx raised where a test expected one: its type and message."""

    def __init__(self, name: str, message: str):
        super().__init__(message)
        self.name = name


class Expected:
    """What Jx rendered in one test, handed out in order."""

    def __init__(self, key: str):
        self.key = key
        self.values = list(EXPECTED.get(key, []))
        self.used = 0

    def next(self) -> dict:
        assert self.used < len(self.values), f"{self.key}: no more recorded Jx results"
        value = self.values[self.used]
        self.used += 1
        return value

    def html(self) -> str:
        value = self.next()
        if "error" in value:
            raise JxError(value["error"], value["message"])
        return value["html"]

    def error(self) -> JxError:
        value = self.next()
        assert "error" in value, f"{self.key}: Jx rendered {value['html']!r}, no error"
        return JxError(value["error"], value["message"])

    def check_all_used(self) -> None:
        assert self.used == len(self.values), (
            f"{self.key}: {len(self.values) - self.used} recorded Jx results not used"
        )


class Project:
    """
    A folder of .jx files compiled by the views compiler, with or without
    autoescape, and what Jx renders for it (`Expected`).
    """

    def __init__(self, root: Path, expected: Expected, autoescape: bool = False):
        self.root = root
        self.autoescape = autoescape
        self.expected = expected
        self.mini = root / "mini"
        self.mini.mkdir()

    def write(self, files: dict[str, str]) -> "Project":
        for name, source in files.items():
            p = self.mini / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(source, encoding="utf-8")
        return self

    def compile(self) -> subprocess.CompletedProcess:
        if self.autoescape:
            return run_minijx(self.mini)  # the default: html, jx, xml
        return run_minijx("--autoescape=", self.mini)

    def render_mini(self, template: str, globals=None, filters=None, tests=None, **kwargs) -> str:
        result = self.compile()
        assert result.returncode == 0, result.stderr
        if filters or tests:
            from proper.views import Catalog

            catalog = Catalog(
                self.mini, compiler=False, filters=filters, tests=tests, autoescape=self.autoescape
            )
            return catalog.render(template, globals=globals, **kwargs)
        mod = load_module(self.mini / (template[:-3] + ".py"))
        return mod.render(_globals=globals, **kwargs)

    def render_jx(self, template: str, **kwargs) -> str:
        """What Jx rendered here (recorded)."""
        return self.expected.html()

    def jx_error(self) -> JxError:
        """The error Jx raised here (recorded)."""
        return self.expected.error()

    def assert_same(self, template: str, globals=None, filters=None, tests=None, **kwargs) -> str:
        """Same HTML as Jx, byte for byte."""
        mini = self.render_mini(template, globals=globals, filters=filters, tests=tests, **kwargs)
        jx = self.render_jx(template)
        assert mini == jx, f"\nminijx: {mini!r}\njx:     {jx!r}"
        return mini
