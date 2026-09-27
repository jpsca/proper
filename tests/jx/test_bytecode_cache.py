"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import jinja2
import pytest
from jinja2.sandbox import SandboxedEnvironment

from proper.jx import Catalog


class DictBytecodeCache(jinja2.BytecodeCache):
    """An in-process stand-in for a cache that would outlive the process."""

    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.loads = 0
        self.dumps = 0

    def load_bytecode(self, bucket):
        data = self.store.get(bucket.key)
        if data is not None:
            self.loads += 1
            import io

            bucket.load_bytecode(io.BytesIO(data))

    def dump_bytecode(self, bucket):
        import io

        out = io.BytesIO()
        bucket.write_bytecode(out)
        self.store[bucket.key] = out.getvalue()
        self.dumps += 1


@pytest.fixture()
def counted(monkeypatch):
    """Count how many times Jinja actually compiles anything."""
    calls = {"n": 0}
    original = jinja2.Environment.compile

    def counting(self, source, name=None, filename=None, raw=False, defer_init=False):
        calls["n"] += 1
        return original(self, source, name, filename, raw, defer_init)

    monkeypatch.setattr(jinja2.Environment, "compile", counting)
    return calls


def write_card(folder, body="<div>{{ t }}</div>"):
    (folder / "card.jx").write_text("{# def t: str #}" + body)


def test_without_a_cache_nothing_changes(folder, counted):
    write_card(folder)
    for _ in range(3):
        Catalog(folder, auto_reload=False).render("card.jx", t="x")
    assert counted["n"] == 3


def test_a_second_catalog_reuses_the_cached_bytecode(folder, counted):
    write_card(folder)
    bcc = DictBytecodeCache()

    first = Catalog(folder, auto_reload=False, bytecode_cache=bcc)
    assert first.render("card.jx", t="a") == "<div>a</div>"
    assert counted["n"] == 1
    assert bcc.dumps == 1

    # A fresh Catalog stands in for a fresh process: nothing in memory, but the
    # cache is still there.
    second = Catalog(folder, auto_reload=False, bytecode_cache=bcc)
    assert second.render("card.jx", t="b") == "<div>b</div>"
    assert counted["n"] == 1, "it compiled again instead of using the cache"
    assert bcc.loads == 1


def test_in_memory_caching_still_applies(folder, counted):
    write_card(folder)
    bcc = DictBytecodeCache()
    catalog = Catalog(folder, auto_reload=False, bytecode_cache=bcc)
    for _ in range(5):
        catalog.render("card.jx", t="x")
    assert counted["n"] == 1
    assert bcc.loads == 0, "the memory cache should answer before the bytecode one"


def test_an_edited_component_invalidates_its_entry(folder, counted):
    write_card(folder, "<div>{{ t }}</div>")
    bcc = DictBytecodeCache()
    assert Catalog(folder, bytecode_cache=bcc).render("card.jx", t="a") == "<div>a</div>"

    write_card(folder, "<p>{{ t }}</p>")
    result = Catalog(folder, bytecode_cache=bcc).render("card.jx", t="a")
    assert result == "<p>a</p>"
    assert counted["n"] == 2


def test_changing_the_environment_invalidates_the_entry(folder):
    """
    Jinja keys a bucket by name and source only. Two catalogs that generate the
    same source but compile it differently must not share an entry.
    """
    (folder / "card.jx").write_text("{# def t: str #}<div>{{ t }}</div>")
    bcc = DictBytecodeCache()

    escaping = Catalog(folder, auto_reload=False, bytecode_cache=bcc)
    assert escaping.render("card.jx", t="<b>") == "<div>&lt;b&gt;</div>"

    env = jinja2.Environment(autoescape=False, undefined=jinja2.StrictUndefined)
    plain = Catalog(folder, jinja_env=env, auto_reload=False, bytecode_cache=bcc)
    assert plain.render("card.jx", t="<b>") == "<div><b></div>"
    assert len(bcc.store) == 2, "both settings ended up in the same bucket"


def test_trim_blocks_invalidates_the_entry(folder):
    """
    `trim_blocks` changes what the lexer keeps, not the source, so it has to be
    part of the fingerprint too.
    """
    (folder / "card.jx").write_text("<div>{% if True %}\nhi{% endif %}</div>")
    bcc = DictBytecodeCache()

    keep = Catalog(folder, auto_reload=False, bytecode_cache=bcc)
    assert keep.render("card.jx") == "<div>\nhi</div>"

    env = jinja2.Environment(
        trim_blocks=True, autoescape=True, undefined=jinja2.StrictUndefined
    )
    trim = Catalog(folder, jinja_env=env, auto_reload=False, bytecode_cache=bcc)
    assert trim.render("card.jx") == "<div>hi</div>"
    assert len(bcc.store) == 2, "both settings ended up in the same bucket"


def test_an_env_that_already_carries_a_cache_is_used(folder, counted):
    write_card(folder)
    bcc = DictBytecodeCache()
    env = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)
    env.bytecode_cache = bcc

    Catalog(folder, jinja_env=env, auto_reload=False).render("card.jx", t="a")
    assert bcc.dumps == 1

    env2 = jinja2.Environment(autoescape=True, undefined=jinja2.StrictUndefined)
    env2.bytecode_cache = bcc
    Catalog(folder, jinja_env=env2, auto_reload=False).render("card.jx", t="b")
    assert counted["n"] == 1


def test_filesystem_cache_end_to_end(folder, tmp_path, counted):
    write_card(folder)
    directory = tmp_path / "bc"
    directory.mkdir()
    bcc = jinja2.FileSystemBytecodeCache(directory=str(directory))

    assert Catalog(folder, auto_reload=False, bytecode_cache=bcc).render(
        "card.jx", t="a"
    ) == "<div>a</div>"
    assert list(directory.iterdir()), "nothing was written to disk"

    assert Catalog(folder, auto_reload=False, bytecode_cache=bcc).render(
        "card.jx", t="b"
    ) == "<div>b</div>"
    assert counted["n"] == 1


def test_children_are_cached_too(folder, counted):
    (folder / "icon.jx").write_text("{# def name: str #}<i>{{ name }}</i>")
    (folder / "card.jx").write_text(
        '{# def t: str #}{# import "icon.jx" as Icon #}<div><Icon name="x" />{{ t }}</div>'
    )
    bcc = DictBytecodeCache()

    assert Catalog(folder, auto_reload=False, bytecode_cache=bcc).render(
        "card.jx", t="a"
    ) == "<div><i>x</i>a</div>"
    assert counted["n"] == 2

    assert Catalog(folder, auto_reload=False, bytecode_cache=bcc).render(
        "card.jx", t="b"
    ) == "<div><i>x</i>b</div>"
    assert counted["n"] == 2


def test_a_sandboxed_env_does_not_share_a_bucket(folder):
    """
    Sandboxing is a codegen decision: an intercepted operator compiles to a
    `call_binop` the plain compiler never emits. Sharing a bucket would hand
    sandboxed rendering code that skips the sandbox's own hooks.
    """
    plain = Catalog(folder, jinja_env=jinja2.Environment(autoescape=True))
    sandboxed = Catalog(
        folder, jinja_env=SandboxedEnvironment(autoescape=True)
    )
    assert plain._fingerprint_env() != sandboxed._fingerprint_env()


def test_the_fingerprint_does_not_depend_on_object_identity(folder):
    """
    `str()` on a callable includes its memory address. A fingerprint built on
    that differs in every worker process, so a shared filesystem or memcached
    cache would never hit — the exact case `select_autoescape` puts users in.
    """
    one = Catalog(folder, jinja_env=jinja2.Environment(
        autoescape=jinja2.select_autoescape()
    ))
    two = Catalog(folder, jinja_env=jinja2.Environment(
        autoescape=jinja2.select_autoescape()
    ))
    assert one._fingerprint_env() == two._fingerprint_env()


def test_differently_configured_autoescape_still_differs(folder):
    """Stable is not enough; it still has to tell the two apart."""
    html = Catalog(folder, jinja_env=jinja2.Environment(
        autoescape=jinja2.select_autoescape(enabled_extensions=("html",))
    ))
    xml = Catalog(folder, jinja_env=jinja2.Environment(
        autoescape=jinja2.select_autoescape(enabled_extensions=("xml",))
    ))
    assert html._fingerprint_env() != xml._fingerprint_env()
