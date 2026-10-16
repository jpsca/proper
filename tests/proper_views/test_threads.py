"""
Concurrent renders. On a free-threaded Python (3.14t with PYTHON_GIL=0)
these run truly in parallel.
"""

import os
import sys
import sysconfig
import threading

import pytest

from proper.views import Catalog
from .helpers import BIN


THREADS = 8
RENDERS = 150

COMPONENTS = {
    "item.jx": """{# def v, i #}
{% do attrs.add_class("item", "n" ~ i) %}
<li {{ attrs.render() }}>{{ v | shout }}{% slot extra %}{% endslot %}</li>""",
    "page.jx": """{# import "item.jx" as Item #}
{# def words, n #}
<ul>
{%- for w in words if w is short(n) %}
  <Item v={{ w }} i={{ loop.index }} data-n={{ n }}>{% fill extra %}({{ loop.revindex }}){% endfill %}</Item>
{%- else %}<li>none</li>{% endfor %}
</ul>
{% wrap %}{{ words | map("shout") | join(",") }}{% endwrap %}""",
}


def write(folder, files):
    for name, source in files.items():
        (folder / name).write_text(source, encoding="utf-8")


def make_catalog(folder, **kwargs):
    return Catalog(
        folder,
        filters={"shout": lambda s: str(s).upper() + "!"},
        tests={"short": lambda s, n: len(s) <= n},
        tags={"wrap": lambda *, caller, template: f"[{caller()}]"},
        **kwargs,
    )


def run_threads(worker):
    barrier = threading.Barrier(THREADS)
    errors = []

    def target(k):
        try:
            barrier.wait()
            worker(k)
        except BaseException as err:  # noqa: BLE001
            errors.append(err)

    threads = [threading.Thread(target=target, args=(k,)) for k in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise errors[0]


def test_concurrent_renders_share_one_catalog(tmp_path):
    write(tmp_path, COMPONENTS)
    catalog = make_catalog(tmp_path, compiler=BIN)
    cases = [(["a", "bb", "ccc", "dddd"][: k % 4 + 1], k % 5) for k in range(THREADS)]
    expected = [catalog.render("page.jx", words=w, n=n) for w, n in cases]
    assert "A!" in expected[1] and "<li>none</li>" in expected[0]

    def worker(k):
        words, n = cases[k]
        for _ in range(RENDERS):
            assert catalog.render("page.jx", words=list(words), n=n) == expected[k]

    run_threads(worker)


def test_concurrent_first_loads_compile_once(tmp_path):
    """Threads asking for components that are not compiled yet."""
    files = {f"c{i}.jx": f'{{# def x #}}<p class="c{i}">{{{{ x }}}}</p>' for i in range(THREADS)}
    write(tmp_path, files)
    catalog = make_catalog(tmp_path, compiler=BIN)

    def worker(k):
        for j in range(20):
            name = f"c{(k + j) % THREADS}.jx"
            n = (k + j) % THREADS
            assert catalog.render(name, x=k) == f'<p class="c{n}">{k}</p>'

    run_threads(worker)
    assert sorted(p.name for p in tmp_path.glob("*.py")) == sorted(f"c{i}.py" for i in range(THREADS))


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED") or os.environ.get("PYTHON_GIL") != "0",
    reason="only on a free-threaded Python run with PYTHON_GIL=0",
)
def test_the_gil_is_really_off():
    import jinja2  # noqa: F401  the test dependencies must not bring the GIL back
    import minijx  # noqa: F401

    assert not sys._is_gil_enabled()
