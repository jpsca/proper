"""
The calls of pure globals (`Catalog(pure=...)`, `--pure`): made once per
call site and arguments, and remembered by the module. And the functions of
one piece of output, which return it without a list.
"""

import pytest

from proper.views import Catalog, runtime
from .helpers import BIN


class Counter:
    """A global that counts its calls and says what it was called with."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        kw = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"/{'/'.join(map(str, args))}?{kw}"


def write(folder, files):
    for name, source in files.items():
        p = folder / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")


def catalog(tmp_path, files, *, pure=("u",), **globals_):
    write(tmp_path, files)
    return Catalog(tmp_path, compiler=BIN, pure=pure, **globals_)


def test_a_call_with_constant_arguments_is_made_once(tmp_path):
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "<a href='{{ u('posts', page=1) }}'>"}, u=u)
    assert cat.render("a.jx") == "<a href='/posts?page=1'>"
    assert cat.render("a.jx") == "<a href='/posts?page=1'>"
    assert u.calls == 1


def test_a_call_with_simple_values_is_made_once_per_value(tmp_path):
    u = Counter()
    cat = catalog(
        tmp_path,
        {"a.jx": "{% for n in ns %}[{{ u('post', id=n, x=s) }}]{% endfor %}"},
        u=u,
    )
    out = cat.render("a.jx", globals={"ns": [1, 2, 1, "1", None, None], "s": "a"})
    assert out == "[/post?id=1,x=a][/post?id=2,x=a][/post?id=1,x=a][/post?id=1,x=a]" \
        "[/post?id=None,x=a][/post?id=None,x=a]"
    assert u.calls == 4  # 1, 2, "1", None
    cat.render("a.jx", globals={"ns": [1, 2], "s": "a"})
    assert u.calls == 4


@pytest.mark.parametrize("value, equal", [(True, 1), (False, 0), (1.0, 1), (2.5, 2.5)])
def test_a_bool_or_a_float_is_called_each_time(tmp_path, value, equal):
    """`True == 1` and `1.0 == 1` (same hash too), but `str(True)` is not
    "1": they are not remembered, and don't get an int's URL."""
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{% for v in vs %}[{{ u(v) }}]{% endfor %}"}, u=u)
    out = cat.render("a.jx", globals={"vs": [equal, value, value]})
    assert out == f"[/{equal}?][/{value}?][/{value}?]"
    assert u.calls == 3


def test_a_call_with_an_object_is_made_each_time(tmp_path):
    class Post:
        id = 7

    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('post', p) }}"}, u=u)
    post = Post()
    cat.render("a.jx", globals={"p": post})
    cat.render("a.jx", globals={"p": post})
    assert u.calls == 2


def test_a_value_that_cannot_be_a_key_is_called_each_time(tmp_path):
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('tags', tags=t) }}"}, u=u)
    assert cat.render("a.jx", globals={"t": ["a", "b"]}) == "/tags?tags=[&#39;a&#39;, &#39;b&#39;]"
    cat.render("a.jx", globals={"t": ["a", "b"]})
    assert u.calls == 2


def test_the_results_kept_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "MAX_PURE", 2)
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{% for n in ns %}{{ u(n) }}{% endfor %}"}, u=u)
    cat.render("a.jx", globals={"ns": [1, 2, 3]})
    assert u.calls == 3
    cat.render("a.jx", globals={"ns": [1, 2, 3]})
    assert u.calls == 4  # 3 was not kept


def test_keyword_arguments_named_like_python_keywords(tmp_path):
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('x', class=c, n=1) }}|{{ u('y', class='k') }}"}, u=u)
    assert cat.render("a.jx", globals={"c": "big"}) == "/x?class=big,n=1|/y?class=k"


def test_each_argument_is_evaluated_once(tmp_path):
    class Item:
        reads = 0

        @property
        def id(self):
            Item.reads += 1
            return 3

    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('item', id=item.id) }}"}, u=u)
    assert cat.render("a.jx", globals={"item": Item()}) == "/item?id=3"
    assert Item.reads == 1


def test_other_globals_are_called_each_time(tmp_path):
    u, v = Counter(), Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('a') }}{{ v('b') }}"}, u=u, v=v)
    cat.render("a.jx")
    cat.render("a.jx")
    assert (u.calls, v.calls) == (1, 2)


def test_without_pure_globals_nothing_is_cached(tmp_path):
    u = Counter()
    cat = catalog(tmp_path, {"a.jx": "{{ u('a') }}"}, pure=(), u=u)
    cat.render("a.jx")
    cat.render("a.jx")
    assert u.calls == 2
    assert "_P[" not in (tmp_path / "a.py").read_text()


def test_each_catalog_has_its_own_results(tmp_path):
    write(tmp_path, {"a.jx": "{{ u('a') }}"})
    one, two = Counter(), Counter()
    Catalog(tmp_path, compiler=BIN, pure=("u",), u=one).render("a.jx")
    assert Catalog(tmp_path, compiler=BIN, pure=("u",), u=two).render("a.jx") == "/a?"
    assert (one.calls, two.calls) == (1, 1)


def test_a_module_compiled_with_other_pure_globals_is_compiled_again(tmp_path):
    u = Counter()
    write(tmp_path, {"a.jx": "{{ u('a') }}"})
    Catalog(tmp_path, compiler=BIN, pure=(), u=u).render("a.jx")
    assert "PURE = ()" in (tmp_path / "a.py").read_text()
    Catalog(tmp_path, compiler=BIN, pure=("u",), u=u).render("a.jx")
    assert "PURE = ('u', )" in (tmp_path / "a.py").read_text()


def test_pure_names_must_be_python_names(tmp_path):
    import subprocess

    result = subprocess.run([str(BIN), "--pure=url-for", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "cannot be a pure global" in result.stderr


# --- functions of one piece ---


def source_of(cat, tmp_path, name):
    cat.compile()
    return (tmp_path / name).read_text()


def test_one_piece_is_returned_without_a_list(tmp_path):
    cat = catalog(tmp_path, {"a.jx": "{# def x #}\n\n  <p>{{ x }}</p>\n", "b.jx": '{# import "a.jx" as A #}\n<A x="1" />'})
    assert cat.render("a.jx", x=1) == "<p>1</p>"
    assert cat.render("b.jx") == "<p>1</p>"
    a = source_of(cat, tmp_path, "a.py")
    assert "_b = []" not in a and ".lstrip()" not in a and "_lstrip" not in a.split("_lstrip = ")[1]
    b = source_of(cat, tmp_path, "b.py")
    assert "    return (_c_" in b


def test_an_expression_first_is_stripped_when_rendering(tmp_path):
    cat = catalog(tmp_path, {"a.jx": "{{ x }}<p></p>"})
    assert cat.render("a.jx", globals={"x": "  a"}) == "a<p></p>"
    assert "return _lstrip(" in source_of(cat, tmp_path, "a.py")


@pytest.mark.parametrize("space", ["　", "\xa0", "\x1c", "\x0b"])
def test_leading_unicode_whitespace_is_still_stripped(tmp_path, space):
    """`str.lstrip()` strips more than ASCII whitespace."""
    cat = catalog(tmp_path, {"a.jx": f"{space} <p>x</p>"})
    assert space.isspace()
    assert cat.render("a.jx") == "<p>x</p>"


def test_an_empty_component(tmp_path):
    cat = catalog(tmp_path, {"a.jx": "  \n", "b.jx": "{# def x #}"})
    assert cat.render("a.jx") == ""
    assert cat.render("b.jx", x=1) == ""


def test_many_pieces_keep_the_list(tmp_path):
    cat = catalog(tmp_path, {"a.jx": " {% if x %} a{% endif %}b", "b.jx": " <p>{% if x %}a{% endif %}"})
    assert cat.render("a.jx", globals={"x": True}) == "ab"
    assert cat.render("b.jx", globals={"x": True}) == "<p>a"
    a = source_of(cat, tmp_path, "a.py")
    assert "_b = []" in a and 'return "".join(_b).lstrip()' in a  # starts with an if
    b = source_of(cat, tmp_path, "b.py")
    assert "_b = []" in b and 'return "".join(_b)\n' in b  # starts with "<p>"


def test_an_empty_attrs_renders_nothing():
    from proper.views import Attrs

    empty = Attrs({})
    assert empty.render() == "" and empty.render() is empty.render()
    # with arguments that leave nothing to render
    assert Attrs({}).render(hidden=False, title=None) == ""
    assert Attrs({"class": "a"}).render() == 'class="a"'
