"""
The compiler is built with Proper's native code, the modules it generates
import `proper.views`, and a module that can't be imported (from an older
version) is compiled again.
"""

import os
import re
import subprocess

from proper.views import Catalog
from proper.views.catalog import MODULE_FORMAT, bundled_compiler
from .helpers import BIN


def test_the_compiler_is_built_with_proper():
    assert BIN is not None
    assert BIN.parent.name == "_native"
    assert bundled_compiler() == BIN


def test_the_compiler_makes_modules_this_runtime_loads():
    out = subprocess.run([str(BIN), "--version"], capture_output=True, text=True).stdout
    m = re.match(r"jxc (\S+) \(module format (\d+)\)", out)
    assert m, out
    assert int(m.group(2)) == MODULE_FORMAT


def test_modules_import_proper_views(tmp_path):
    (tmp_path / "a.jx").write_text("{# def n #}<p>{{ n }}</p>")
    Catalog(tmp_path, compiler=BIN).compile()
    source = (tmp_path / "a.py").read_text()
    assert "from proper.views.runtime import" in source
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert imports
    assert all(line.startswith(("from proper.views.", "from __future__ ")) for line in imports)


def test_a_module_that_cannot_be_imported_is_compiled_again(tmp_path):
    """A module of an older version imports a runtime that is gone: it is
    stale, not an error."""
    (tmp_path / "a.jx").write_text("{# def n #}<p>{{ n }}</p>")
    py = tmp_path / "a.py"
    py.write_text("from gone.runtime import escape_output as _e\nVIEWS_FORMAT = 9\n")
    # newer than its .jx, as a module that is up to date
    jx_mtime = (tmp_path / "a.jx").stat().st_mtime
    os.utime(py, (jx_mtime + 10, jx_mtime + 10))

    assert Catalog(tmp_path, compiler=BIN).render("a.jx", n=3) == "<p>3</p>"
    assert "from proper.views.runtime import" in py.read_text()
