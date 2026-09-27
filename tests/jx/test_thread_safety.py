"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import os
import time
from threading import Event, Thread, current_thread

from proper.jx import Catalog
from proper.jx.component import Component


class ThreadWithReturnValue(Thread):
    def __init__(self, group=None, target=None, name=None, args=None, kwargs=None):
        args = args or ()
        kwargs = kwargs or {}
        Thread.__init__(
            self,
            group=group,
            target=target,
            name=name,
            args=args,
            kwargs=kwargs,
        )
        self._target = target
        self._args = args
        self._kwargs = kwargs
        self._return = None

    def run(self):
        if self._target is not None:
            self._return = self._target(*self._args, **self._kwargs)

    def join(self, *args, **kwargs):
        Thread.join(self, *args, **kwargs)
        return self._return


def test_thread_safety_of_render_assets(folder):
    NUM_THREADS = 5

    child_tmpl = """
{#css "/static/c{i}.css" #}
{#js "/static/c{i}.js" #}
<p>Child {i}</p>""".strip()

    parent_tmpl = """
{{ assets.render() }}
{{ content }}""".strip()

    comp_tmpl = """
{# import "parent{i}.jx" as Parent{i} #}
{# import "child{i}.jx" as Child{i} #}
{# css "/static/a{i}.css", "/static/b{i}.css" #}
{# js "/static/a{i}.js", "/static/b{i}.js" #}
<Parent{i}><Child{i} /></Parent{i}>""".strip()

    expected_tmpl = """
<link rel="stylesheet" href="/static/a{i}.css">
<link rel="stylesheet" href="/static/b{i}.css">
<link rel="stylesheet" href="/static/c{i}.css">
<script type="module" src="/static/a{i}.js"></script>
<script type="module" src="/static/b{i}.js"></script>
<script type="module" src="/static/c{i}.js"></script>
<p>Child {i}</p>""".strip()

    for i in range(NUM_THREADS):
        si = str(i)
        child_name = f"child{i}.jx"
        child_src = child_tmpl.replace("{i}", si)

        parent_name = f"parent{i}.jx"
        parent_src = parent_tmpl.replace("{i}", si)

        comp_name = f"page{i}.jx"
        comp_src = comp_tmpl.replace("{i}", si)

        (folder / child_name).write_text(child_src)
        (folder / comp_name).write_text(comp_src)
        (folder / parent_name).write_text(parent_src)

    cat = Catalog(folder)

    def render(i):
        return cat.render(f"page{i}.jx")

    threads = []

    for i in range(NUM_THREADS):
        thread = ThreadWithReturnValue(target=render, args=(i,))
        threads.append(thread)
        thread.start()

    results = [thread.join() for thread in threads]

    for i, result in enumerate(results):
        expected = expected_tmpl.replace("{i}", str(i))
        print(f"---- EXPECTED {i}----")
        print(expected)
        print(f"---- RESULT {i}----")
        print(result)
        assert result == expected


def test_thread_safety_of_template_globals(folder):
    NUM_THREADS = 5
    (folder / "page.jx").write_text(
        "{{ globalvar if globalvar is defined else 'not set' }}"
    )

    cat = Catalog(folder)

    def render(i):
        return cat.render("page.jx", globals={"globalvar": i})

    threads = []

    for i in range(NUM_THREADS):
        thread = ThreadWithReturnValue(target=render, args=(i,))
        threads.append(thread)
        thread.start()

    results = [thread.join() for thread in threads]

    for i, result in enumerate(results):
        assert result == str(i)


def test_asset_cache_not_poisoned_by_concurrent_reload(folder):
    """
    A `collect_css()` in flight must not write its now-stale result into the
    shared asset cache after another thread has invalidated it by reloading
    the component. Otherwise the stale list survives forever, because nothing
    invalidates the cache again until some *other* component changes.
    """
    comp = folder / "page.jx"
    comp.write_text('{#css "v1.css" #}\n<p>page</p>')

    gate = Event()

    class GatedComponent(Component):
        def _collect_assets(self, attr, _visited=None):
            result = super()._collect_assets(attr, _visited=_visited)
            if _visited is None:
                # Top-level call: hold here so the reload lands in the window
                # between computing the result and storing it.
                gate.wait(5)
            return result

    class GatedCatalog(Catalog):
        def get_component(self, relpath):
            co = super().get_component(relpath)
            gated = GatedComponent(
                relpath=co.relpath,
                tmpl=co.tmpl,
                get_component=self.get_component,
                required=co.required,
                optional=co.optional,
                imports=co.imports,
                css=co.css,
                js=co.js,
                slots=co.slots,
                asset_cache=co._asset_cache,
            )
            return gated

    catalog = GatedCatalog(folder, auto_reload=True)
    collector = ThreadWithReturnValue(target=catalog.get_component("page.jx").collect_css)
    collector.start()

    # Meanwhile the file changes; the reload must invalidate the asset cache.
    comp.write_text('{#css "v2.css" #}\n<p>page</p>')
    os.utime(comp, (time.time() + 10, time.time() + 10))
    assert catalog.get_signature("page.jx")["css"] == ("v2.css",)

    gate.set()
    collector.join()

    assert catalog.get_component("page.jx").collect_css() == ["v2.css"]


def test_component_snapshot_is_consistent_during_concurrent_reload(folder):
    """
    `get_component()` reads nine fields off the `CData` it just looked up.
    A reload must therefore publish a whole new `CData` rather than rebinding
    the fields of the live one -- otherwise a reload landing between those reads
    hands back a `Component` built from two different versions of the file
    (e.g. the old `tmpl` paired with the new `required`).
    """
    comp = folder / "a.jx"
    comp.write_text("{#def name #}\n<p>{{ name }}</p>")

    gate = Event()
    reached = Event()

    class GatedCatalog(Catalog):
        def get_component_data(self, relpath):
            cdata = super().get_component_data(relpath)
            if current_thread().name == "reader":
                # Sits between "CData obtained" and "CData fields read".
                reached.set()
                gate.wait(5)
            return cdata

    catalog = GatedCatalog(folder, auto_reload=True)
    catalog.render("a.jx", name="x")  # warm the cache

    reader = ThreadWithReturnValue(
        target=lambda: catalog.get_component("a.jx").render(name="x")
    )
    reader.name = "reader"
    reader.start()
    reached.wait(5)

    # The file changes and another thread reloads it while the reader is
    # part-way through building its Component.
    comp.write_text("{#def title #}\n<p>{{ title }}</p>")
    os.utime(comp, (time.time() + 10, time.time() + 10))
    writer = Thread(target=catalog.get_component_data, args=("a.jx",))
    writer.start()
    time.sleep(0.2)

    gate.set()
    assert reader.join() == "<p>x</p>"
    writer.join()
    assert catalog.get_signature("a.jx")["required"] == {"title": None}
