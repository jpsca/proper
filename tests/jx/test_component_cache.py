"""
Jx | Copyright (c) Juan-Pablo Scaletti

`Catalog.get_component` used to build a new `Component` on every access to a
child, because rendering assigned the render tree's globals to the instance.
Globals are passed to `render` now, so a component is immutable and one
instance serves every render of it.
"""

import os
import threading
import time

import pytest

from proper.jx import Catalog
from proper.jx.component import Component


def test_the_same_instance_is_returned(folder):
    (folder / "card.jx").write_text("{# def t: str #}<b>{{ t }}</b>")
    catalog = Catalog(folder, auto_reload=False)
    assert catalog.get_component("card.jx") is catalog.get_component("card.jx")


def test_a_component_carries_no_render_state(folder):
    """If it did, sharing one instance between renders would leak between them."""
    (folder / "card.jx").write_text("{# def t: str #}<b>{{ t }}</b>")
    component = Catalog(folder, auto_reload=False).get_component("card.jx")
    assert not hasattr(component, "globals")
    assert "globals" not in Component.__slots__


def test_an_edit_replaces_the_instance(folder):
    path = folder / "card.jx"
    path.write_text("{# def t: str #}<b>{{ t }}</b>")
    catalog = Catalog(folder, auto_reload=True)
    first = catalog.get_component("card.jx")

    path.write_text("{# def t: str #}<i>{{ t }}</i>")
    os.utime(path, (time.time() + 10, time.time() + 10))

    second = catalog.get_component("card.jx")
    assert second is not first
    assert second.render(t="x") == "<i>x</i>"


def test_an_edit_to_a_child_does_not_serve_a_stale_parent(folder):
    """
    A cached component holds the asset cache that was live when it was built,
    so recompiling anything has to drop the cached components too.
    """
    child = folder / "child.jx"
    child.write_text('{#css "v1.css" #}<i>c</i>')
    (folder / "parent.jx").write_text(
        '{# import "child.jx" as Child #}<div><Child /></div>'
    )
    catalog = Catalog(folder, auto_reload=True)
    assert catalog.get_component("parent.jx").collect_css() == ["v1.css"]

    child.write_text('{#css "v2.css" #}<i>c</i>')
    os.utime(child, (time.time() + 10, time.time() + 10))

    assert catalog.get_component("parent.jx").collect_css() == ["v2.css"]


def test_globals_do_not_leak_between_concurrent_renders(folder):
    """
    Two threads render the same component through the same shared instance,
    each with its own globals. Neither may see the other's.
    """
    (folder / "leaf.jx").write_text("[{{ who }}]")
    (folder / "page.jx").write_text('{# import "leaf.jx" as Leaf #}<Leaf /><Leaf />')
    catalog = Catalog(folder, auto_reload=False)

    results: dict[str, str] = {}
    started = threading.Barrier(2)

    def run(who: str) -> None:
        started.wait()
        for _ in range(50):
            results[who] = catalog.render("page.jx", globals={"who": who})

    threads = [threading.Thread(target=run, args=(w,)) for w in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == {"a": "[a][a]", "b": "[b][b]"}


def test_recursion_depth_still_counts(folder):
    """Depth lives in the globals of a render tree, not on the instance."""
    (folder / "loop.jx").write_text('{# import "loop.jx" as Loop #}<Loop />')
    catalog = Catalog(folder, auto_reload=False)
    with pytest.raises(Exception, match="recursion|depth"):
        catalog.render("loop.jx")


def test_reused_instance_does_not_accumulate_depth(folder):
    """Rendering the same component twice must start at the same depth."""
    (folder / "leaf.jx").write_text("x")
    (folder / "page.jx").write_text('{# import "leaf.jx" as Leaf #}<Leaf /><Leaf />')
    catalog = Catalog(folder, auto_reload=False)
    for _ in range(200):
        assert catalog.render("page.jx") == "xx"


def test_editing_a_child_invalidates_the_parent_asset_list(folder):
    """
    The cached list covers the whole subtree, so the parent being unchanged
    says nothing about whether it is still right. Once everything is warm,
    nothing would otherwise look at the child again.
    """
    (folder / "child.jx").write_text('{#css "old.css" #}<p>c</p>')
    (folder / "parent.jx").write_text(
        '{#import "child.jx" as Child #}{{ assets.render_css() }}<Child />'
    )
    catalog = Catalog(folder)

    def css():
        return catalog.render("parent.jx").split("<p>")[0].strip()

    assert css() == '<link rel="stylesheet" href="old.css">'
    # Again, so every component is warm and the parent's entry survives.
    assert css() == '<link rel="stylesheet" href="old.css">'

    time.sleep(0.05)  # the mtime has to actually differ
    (folder / "child.jx").write_text('{#css "new.css" #}<p>c</p>')

    assert css() == '<link rel="stylesheet" href="new.css">'
