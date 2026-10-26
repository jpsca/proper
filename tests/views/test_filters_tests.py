"""
Every runtime filter and test is compared against jinja2's own.
"""

import types

import jinja2
import pytest

from proper.views import filters as F
from proper.views.tests import TESTS


ENV = jinja2.Environment()
CTX = ENV.from_string("").new_context()


def same(a, b):
    """Generators/iterators compare by content; namedtuples by tuple."""
    if isinstance(a, (types.GeneratorType, map, filter, reversed)) or hasattr(a, "__next__"):
        a = list(a)
    if isinstance(b, (types.GeneratorType, map, filter, reversed)) or hasattr(b, "__next__"):
        b = list(b)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, tuple) and isinstance(b, tuple):
        return tuple(a) == tuple(b)
    return a == b


PEOPLE = [
    {"name": "Ana", "age": 30, "tags": ["x"]},
    {"name": "bob", "age": 25, "tags": []},
    {"name": "Cid", "age": 35, "tags": ["y", "z"]},
]

FILTER_CASES = [
    ("abs", -3, (), {}),
    ("attr", types.SimpleNamespace(x=1), ("x",), {}),
    ("batch", [1, 2, 3, 4, 5], (2,), {}),
    ("batch", [1, 2, 3, 4, 5], (2, 0), {}),
    ("capitalize", "hello WORLD", (), {}),
    ("center", "hi", (10,), {}),
    ("count", [1, 2, 3], (), {}),
    ("default", None, ("x",), {}),
    ("default", None, ("x", True), {}),
    ("default", "", ("x",), {}),
    ("default", "", ("x", True), {}),
    ("default", 0, ("x",), {}),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (), {}),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (True,), {}),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (), {"by": "value", "reverse": True}),
    ("e", "<a href='x'>&\"</a>", (), {}),
    ("filesizeformat", 1000, (), {}),
    ("filesizeformat", 1, (), {}),
    ("filesizeformat", 123456789, (), {}),
    ("filesizeformat", 123456789, (True,), {}),
    ("first", [4, 5], (), {}),
    ("float", "1.5", (), {}),
    ("float", "x", (), {}),
    ("float", "x", (2.0,), {}),
    ("forceescape", "<b>", (), {}),
    ("format", "%s-%d", ("a", 3), {}),
    ("format", "%(a)s", (), {"a": 1}),
    ("groupby", PEOPLE, ("age",), {}),
    ("groupby", [{"g": "A"}, {"g": "a"}, {"g": "b"}], ("g",), {}),
    ("groupby", [{"g": "A"}, {"g": "a"}, {"g": "b"}], ("g",), {"case_sensitive": True}),
    ("indent", "a\nb\n\nc", (), {}),
    ("indent", "a\nb\n\nc", (2, True, True), {}),
    ("indent", "a\nb", ("--",), {}),
    ("int", "42", (), {}),
    ("int", "4.7", (), {}),
    ("int", "x", (9,), {}),
    ("int", "ff", (0, 16), {}),
    ("items", {"a": 1}, (), {}),
    ("join", [1, 2], ("-",), {}),
    ("join", PEOPLE, (", ", "name"), {}),
    ("last", [4, 5], (), {}),
    ("length", "abc", (), {}),
    ("list", "abc", (), {}),
    ("lower", "ABC", (), {}),
    ("map", PEOPLE, (), {"attribute": "name"}),
    ("map", ["a", "b"], ("upper",), {}),
    ("map", [{"a": {"b": 1}}, {"a": {}}], (), {"attribute": "a.b", "default": 0}),
    ("max", [1, 5, 3], (), {}),
    ("max", PEOPLE, (), {"attribute": "age"}),
    ("max", ["a", "B"], (), {}),
    ("max", ["a", "B"], (True,), {}),
    ("min", [1, 5, 3], (), {}),
    ("min", PEOPLE, (), {"attribute": "name"}),
    ("reject", [1, 2, 3, 4], ("odd",), {}),
    ("reject", [0, 1, "", "x"], (), {}),
    ("rejectattr", PEOPLE, ("tags",), {}),
    ("rejectattr", PEOPLE, ("age", "gt", 28), {}),
    ("replace", "aaa", ("a", "b"), {}),
    ("replace", "aaa", ("a", "b", 2), {}),
    ("reverse", "abc", (), {}),
    ("reverse", [1, 2, 3], (), {}),
    ("round", 2.567, (), {}),
    ("round", 2.567, (2,), {}),
    ("round", 2.567, (0, "ceil"), {}),
    ("round", 2.567, (1, "floor"), {}),
    ("safe", "<b>", (), {}),
    ("select", [1, 2, 3, 4], ("even",), {}),
    ("select", [1, 2, 3, 4], ("divisibleby", 4), {}),
    ("select", [0, 1, "", "x"], (), {}),
    ("selectattr", PEOPLE, ("tags",), {}),
    ("selectattr", PEOPLE, ("name", "equalto", "bob"), {}),
    ("slice", [1, 2, 3, 4, 5], (2,), {}),
    ("slice", [1, 2, 3, 4, 5], (3, None), {}),
    ("slice", [1, 2, 3, 4, 5], (3, 0), {}),
    ("sort", [3, 1, 2], (), {}),
    ("sort", ["b", "A", "c"], (), {}),
    ("sort", ["b", "A", "c"], (False, True), {}),
    ("sort", PEOPLE, (), {"attribute": "age", "reverse": True}),
    ("sort", PEOPLE, (), {"attribute": "tags,name"}),
    ("string", 12, (), {}),
    ("striptags", "<p>Hi <b>there</b>&amp;  you</p>", (), {}),
    ("sum", [1, 2, 3], (), {}),
    ("sum", PEOPLE, ("age",), {}),
    ("sum", PEOPLE, ("age", 100), {}),
    ("title", "hello-world foo_bar (baz)", (), {}),
    ("title", "o'neil mcDonald", (), {}),
    ("trim", "  x  ", (), {}),
    ("trim", "xxhixx", ("x",), {}),
    ("truncate", "hello world this is long", (12,), {}),
    ("truncate", "hello world this is long", (12, True), {}),
    ("truncate", "hello world this is long", (12, False, "…", 0), {}),
    ("truncate", "short", (12,), {}),
    ("unique", [1, 2, 1, 3, 2], (), {}),
    ("unique", ["a", "A", "b"], (), {}),
    ("unique", ["a", "A", "b"], (True,), {}),
    ("unique", PEOPLE + [{"name": "ana", "age": 1, "tags": []}], (), {"attribute": "name"}),
    ("upper", "abc", (), {}),
    ("urlencode", "a b/c?d=é", (), {}),
    ("urlencode", {"a": "b c", "d": "é"}, (), {}),
    ("urlencode", [("a", 1), ("b", "x y")], (), {}),
    ("wordcount", "hello big world", (), {}),
    ("wordwrap", "the quick brown fox jumps over the lazy dog", (10,), {}),
    ("wordwrap", "a\nbb ccc dddd eeeee", (5, False), {}),
    ("wordwrap", "aaaaaaaaaa bbb", (4,), {"wrapstring": "|"}),
    ("tojson", {"a": [1, "<b>", "'x'", "&"]}, (), {}),
    ("tojson", {"a": 1}, (2,), {}),
    ("tojson", {"b": 1, "a": {"d": "é", "c": None}}, (), {}),
    ("tojson", {"b": 1, "a": 2}, (2,), {}),
]


@pytest.mark.parametrize("name,value,args,kwargs", FILTER_CASES, ids=lambda x: x if isinstance(x, str) else "")
def test_filter_matches_jinja(name, value, args, kwargs):
    import copy

    expected = ENV.call_filter(name, copy.deepcopy(value), list(args), dict(kwargs), context=CTX)
    actual = getattr(F, name)(copy.deepcopy(value), *args, **kwargs)
    if isinstance(expected, jinja2.runtime.Undefined):
        expected = None
    assert same(actual, expected), (actual, expected)


def test_every_jinja_filter_is_present_except_excluded():
    excluded = {"xmlattr", "pprint", "urlize"}
    missing = set(ENV.filters) - excluded - set(F.FILTERS)
    assert not missing


TEST_CASES = [
    ("odd", 3, ()), ("odd", 4, ()), ("even", 4, ()), ("divisibleby", 9, (3,)), ("divisibleby", 10, (3,)),
    ("none", None, ()), ("none", 0, ()), ("boolean", True, ()), ("boolean", 1, ()),
    ("false", False, ()), ("false", 0, ()), ("true", True, ()), ("true", 1, ()),
    ("integer", 1, ()), ("integer", True, ()), ("integer", 1.0, ()), ("float", 1.0, ()), ("float", 1, ()),
    ("lower", "abc", ()), ("lower", "aBc", ()), ("upper", "ABC", ()), ("upper", "aBc", ()),
    ("string", "x", ()), ("string", 1, ()), ("mapping", {}, ()), ("mapping", [], ()),
    ("number", 1.5, ()), ("number", "1", ()), ("number", True, ()),
    ("sequence", [1], ()), ("sequence", "ab", ()), ("sequence", 1, ()), ("sequence", {"a": 1}, ()),
    ("iterable", [1], ()), ("iterable", 1, ()), ("callable", len, ()), ("callable", 1, ()),
    ("sameas", None, (None,)), ("sameas", 1, (1.0,)), ("escaped", "x", ()),
    ("in", 1, ([1, 2],)), ("in", 3, ([1, 2],)),
    ("==", 1, (1,)), ("eq", 1, (2,)), ("equalto", "a", ("a",)), ("!=", 1, (2,)), ("ne", 1, (1,)),
    (">", 2, (1,)), ("gt", 1, (2,)), ("greaterthan", 3, (2,)), (">=", 2, (2,)), ("ge", 1, (2,)),
    ("<", 1, (2,)), ("lt", 2, (1,)), ("lessthan", 1, (2,)), ("<=", 2, (2,)), ("le", 3, (2,)),
    ("filter", "upper", ()), ("filter", "nope", ()), ("test", "odd", ()), ("test", "nope", ()),
    ("defined", 1, ()), ("undefined", 1, ()),
]


@pytest.mark.parametrize("name,value,args", TEST_CASES, ids=lambda x: x if isinstance(x, str) else "")
def test_test_matches_jinja(name, value, args):
    expected = ENV.call_test(name, value, list(args))
    actual = TESTS[name](value, *args)
    assert actual == expected


def test_every_jinja_test_is_present():
    assert set(ENV.tests) <= set(TESTS)
