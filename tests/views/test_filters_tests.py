"""
Every runtime filter and test is compared with Jinja's own.

What Jinja returns is fixed: each case has, as its last value, what Jinja
3.1.6 returned for it. It was recorded once, from the tests that passed:
each value is one the views matched.
"""

import copy
import types

import pytest

from proper.views import filters as F
from proper.views.tests import TESTS


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
    ("abs", -3, (), {}, 3),
    ("attr", types.SimpleNamespace(x=1), ("x",), {}, 1),
    ("batch", [1, 2, 3, 4, 5], (2,), {}, [[1, 2], [3, 4], [5]]),
    ("batch", [1, 2, 3, 4, 5], (2, 0), {}, [[1, 2], [3, 4], [5, 0]]),
    ("capitalize", "hello WORLD", (), {}, "Hello world"),
    ("center", "hi", (10,), {}, "    hi    "),
    ("count", [1, 2, 3], (), {}, 3),
    ("default", None, ("x",), {}, None),
    ("default", None, ("x", True), {}, "x"),
    ("default", "", ("x",), {}, ""),
    ("default", "", ("x", True), {}, "x"),
    ("default", 0, ("x",), {}, 0),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (), {}, [("A", 2), ("b", 1), ("c", 0)]),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (True,), {}, [("A", 2), ("b", 1), ("c", 0)]),
    ("dictsort", {"b": 1, "A": 2, "c": 0}, (), {"by": "value", "reverse": True}, [("A", 2), ("b", 1), ("c", 0)]),
    ("e", "<a href='x'>&\"</a>", (), {}, "&lt;a href=&#39;x&#39;&gt;&amp;&#34;&lt;/a&gt;"),
    ("filesizeformat", 1000, (), {}, "1.0 kB"),
    ("filesizeformat", 1, (), {}, "1 Byte"),
    ("filesizeformat", 123456789, (), {}, "123.5 MB"),
    ("filesizeformat", 123456789, (True,), {}, "117.7 MiB"),
    ("first", [4, 5], (), {}, 4),
    ("float", "1.5", (), {}, 1.5),
    ("float", "x", (), {}, 0.0),
    ("float", "x", (2.0,), {}, 2.0),
    ("forceescape", "<b>", (), {}, "&lt;b&gt;"),
    ("format", "%s-%d", ("a", 3), {}, "a-3"),
    ("format", "%(a)s", (), {"a": 1}, "1"),
    ("groupby", PEOPLE, ("age",), {}, [(25, [PEOPLE[1]]), (30, [PEOPLE[0]]), (35, [PEOPLE[2]])]),
    ("groupby", [{"g": "A"}, {"g": "a"}, {"g": "b"}], ("g",), {}, [("A", [{"g": "A"}, {"g": "a"}]), ("b", [{"g": "b"}])]),
    ("groupby", [{"g": "A"}, {"g": "a"}, {"g": "b"}], ("g",), {"case_sensitive": True}, [("A", [{"g": "A"}]), ("a", [{"g": "a"}]), ("b", [{"g": "b"}])]),
    ("indent", "a\nb\n\nc", (), {}, "a\n    b\n\n    c"),
    ("indent", "a\nb\n\nc", (2, True, True), {}, "  a\n  b\n  \n  c"),
    ("indent", "a\nb", ("--",), {}, "a\n--b"),
    ("int", "42", (), {}, 42),
    ("int", "4.7", (), {}, 4),
    ("int", "x", (9,), {}, 9),
    ("int", "ff", (0, 16), {}, 255),
    ("items", {"a": 1}, (), {}, [("a", 1)]),
    ("join", [1, 2], ("-",), {}, "1-2"),
    ("join", PEOPLE, (", ", "name"), {}, "Ana, bob, Cid"),
    ("last", [4, 5], (), {}, 5),
    ("length", "abc", (), {}, 3),
    ("list", "abc", (), {}, ["a", "b", "c"]),
    ("lower", "ABC", (), {}, "abc"),
    ("map", PEOPLE, (), {"attribute": "name"}, ["Ana", "bob", "Cid"]),
    ("map", ["a", "b"], ("upper",), {}, ["A", "B"]),
    ("map", [{"a": {"b": 1}}, {"a": {}}], (), {"attribute": "a.b", "default": 0}, [1, 0]),
    ("max", [1, 5, 3], (), {}, 5),
    ("max", PEOPLE, (), {"attribute": "age"}, PEOPLE[2]),
    ("max", ["a", "B"], (), {}, "B"),
    ("max", ["a", "B"], (True,), {}, "a"),
    ("min", [1, 5, 3], (), {}, 1),
    ("min", PEOPLE, (), {"attribute": "name"}, PEOPLE[0]),
    ("reject", [1, 2, 3, 4], ("odd",), {}, [2, 4]),
    ("reject", [0, 1, "", "x"], (), {}, [0, ""]),
    ("rejectattr", PEOPLE, ("tags",), {}, [PEOPLE[1]]),
    ("rejectattr", PEOPLE, ("age", "gt", 28), {}, [PEOPLE[1]]),
    ("replace", "aaa", ("a", "b"), {}, "bbb"),
    ("replace", "aaa", ("a", "b", 2), {}, "bba"),
    ("reverse", "abc", (), {}, "cba"),
    ("reverse", [1, 2, 3], (), {}, [3, 2, 1]),
    ("round", 2.567, (), {}, 3.0),
    ("round", 2.567, (2,), {}, 2.57),
    ("round", 2.567, (0, "ceil"), {}, 3.0),
    ("round", 2.567, (1, "floor"), {}, 2.5),
    ("safe", "<b>", (), {}, "<b>"),
    ("select", [1, 2, 3, 4], ("even",), {}, [2, 4]),
    ("select", [1, 2, 3, 4], ("divisibleby", 4), {}, [4]),
    ("select", [0, 1, "", "x"], (), {}, [1, "x"]),
    ("selectattr", PEOPLE, ("tags",), {}, [PEOPLE[0], PEOPLE[2]]),
    ("selectattr", PEOPLE, ("name", "equalto", "bob"), {}, [PEOPLE[1]]),
    ("slice", [1, 2, 3, 4, 5], (2,), {}, [[1, 2, 3], [4, 5]]),
    ("slice", [1, 2, 3, 4, 5], (3, None), {}, [[1, 2], [3, 4], [5]]),
    ("slice", [1, 2, 3, 4, 5], (3, 0), {}, [[1, 2], [3, 4], [5, 0]]),
    ("sort", [3, 1, 2], (), {}, [1, 2, 3]),
    ("sort", ["b", "A", "c"], (), {}, ["A", "b", "c"]),
    ("sort", ["b", "A", "c"], (False, True), {}, ["A", "b", "c"]),
    ("sort", PEOPLE, (), {"attribute": "age", "reverse": True}, [PEOPLE[2], PEOPLE[0], PEOPLE[1]]),
    ("sort", PEOPLE, (), {"attribute": "tags,name"}, [PEOPLE[1], PEOPLE[0], PEOPLE[2]]),
    ("string", 12, (), {}, "12"),
    ("striptags", "<p>Hi <b>there</b>&amp;  you</p>", (), {}, "Hi there& you"),
    ("sum", [1, 2, 3], (), {}, 6),
    ("sum", PEOPLE, ("age",), {}, 90),
    ("sum", PEOPLE, ("age", 100), {}, 190),
    ("title", "hello-world foo_bar (baz)", (), {}, "Hello-World Foo_bar (Baz)"),
    ("title", "o'neil mcDonald", (), {}, "O'neil Mcdonald"),
    ("trim", "  x  ", (), {}, "x"),
    ("trim", "xxhixx", ("x",), {}, "hi"),
    ("truncate", "hello world this is long", (12,), {}, "hello..."),
    ("truncate", "hello world this is long", (12, True), {}, "hello wor..."),
    ("truncate", "hello world this is long", (12, False, "…", 0), {}, "hello…"),
    ("truncate", "short", (12,), {}, "short"),
    ("unique", [1, 2, 1, 3, 2], (), {}, [1, 2, 3]),
    ("unique", ["a", "A", "b"], (), {}, ["a", "b"]),
    ("unique", ["a", "A", "b"], (True,), {}, ["a", "A", "b"]),
    ("unique", PEOPLE + [{"name": "ana", "age": 1, "tags": []}], (), {"attribute": "name"}, [PEOPLE[0], PEOPLE[1], PEOPLE[2]]),
    ("upper", "abc", (), {}, "ABC"),
    ("urlencode", "a b/c?d=é", (), {}, "a%20b/c%3Fd%3D%C3%A9"),
    ("urlencode", {"a": "b c", "d": "é"}, (), {}, "a=b+c&d=%C3%A9"),
    ("urlencode", [("a", 1), ("b", "x y")], (), {}, "a=1&b=x+y"),
    ("wordcount", "hello big world", (), {}, 3),
    ("wordwrap", "the quick brown fox jumps over the lazy dog", (10,), {}, "the quick\nbrown fox\njumps over\nthe lazy\ndog"),
    ("wordwrap", "a\nbb ccc dddd eeeee", (5, False), {}, "a\nbb\nccc\ndddd\neeeee"),
    ("wordwrap", "aaaaaaaaaa bbb", (4,), {"wrapstring": "|"}, "aaaa|aaaa|aa|bbb"),
    ("tojson", {"a": [1, "<b>", "'x'", "&"]}, (), {}, '{"a": [1, "\\u003cb\\u003e", "\\u0027x\\u0027", "\\u0026"]}'),
    ("tojson", {"a": 1}, (2,), {}, '{\n  "a": 1\n}'),
    ("tojson", {"b": 1, "a": {"d": "é", "c": None}}, (), {}, '{"a": {"c": null, "d": "\\u00e9"}, "b": 1}'),
    ("tojson", {"b": 1, "a": 2}, (2,), {}, '{\n  "a": 2,\n  "b": 1\n}'),
]


@pytest.mark.parametrize(
    "name,value,args,kwargs,expected",
    FILTER_CASES,
    ids=[case[0] for case in FILTER_CASES],
)
def test_filter_matches_jinja(name, value, args, kwargs, expected):
    actual = getattr(F, name)(copy.deepcopy(value), *args, **kwargs)
    assert same(actual, expected), (actual, expected)


# The filters of a `jinja2.Environment()`
JINJA_FILTERS = (
    "abs", "attr", "batch", "capitalize", "center", "count", "d", "default", "dictsort",
    "e", "escape", "filesizeformat", "first", "float", "forceescape", "format", "groupby",
    "indent", "int", "items", "join", "last", "length", "list", "lower", "map", "max",
    "min", "pprint", "random", "reject", "rejectattr", "replace", "reverse", "round",
    "safe", "select", "selectattr", "slice", "sort", "string", "striptags", "sum",
    "title", "tojson", "trim", "truncate", "unique", "upper", "urlencode", "urlize",
    "wordcount", "wordwrap", "xmlattr",
)


def test_every_jinja_filter_is_present_except_excluded():
    excluded = {"xmlattr", "pprint", "urlize"}
    missing = set(JINJA_FILTERS) - excluded - set(F.FILTERS)
    assert not missing


TEST_CASES = [
    ("odd", 3, (), True), ("odd", 4, (), False), ("even", 4, (), True), ("divisibleby", 9, (3,), True), ("divisibleby", 10, (3,), False),
    ("none", None, (), True), ("none", 0, (), False), ("boolean", True, (), True), ("boolean", 1, (), False),
    ("false", False, (), True), ("false", 0, (), False), ("true", True, (), True), ("true", 1, (), False),
    ("integer", 1, (), True), ("integer", True, (), False), ("integer", 1.0, (), False), ("float", 1.0, (), True), ("float", 1, (), False),
    ("lower", "abc", (), True), ("lower", "aBc", (), False), ("upper", "ABC", (), True), ("upper", "aBc", (), False),
    ("string", "x", (), True), ("string", 1, (), False), ("mapping", {}, (), True), ("mapping", [], (), False),
    ("number", 1.5, (), True), ("number", "1", (), False), ("number", True, (), True),
    ("sequence", [1], (), True), ("sequence", "ab", (), True), ("sequence", 1, (), False), ("sequence", {"a": 1}, (), True),
    ("iterable", [1], (), True), ("iterable", 1, (), False), ("callable", len, (), True), ("callable", 1, (), False),
    ("sameas", None, (None,), True), ("sameas", 1, (1.0,), False), ("escaped", "x", (), False),
    ("in", 1, ([1, 2],), True), ("in", 3, ([1, 2],), False),
    ("==", 1, (1,), True), ("eq", 1, (2,), False), ("equalto", "a", ("a",), True), ("!=", 1, (2,), True), ("ne", 1, (1,), False),
    (">", 2, (1,), True), ("gt", 1, (2,), False), ("greaterthan", 3, (2,), True), (">=", 2, (2,), True), ("ge", 1, (2,), False),
    ("<", 1, (2,), True), ("lt", 2, (1,), False), ("lessthan", 1, (2,), True), ("<=", 2, (2,), True), ("le", 3, (2,), False),
    ("filter", "upper", (), True), ("filter", "nope", (), False), ("test", "odd", (), True), ("test", "nope", (), False),
    ("defined", 1, (), True), ("undefined", 1, (), False),
]


@pytest.mark.parametrize(
    "name,value,args,expected",
    TEST_CASES,
    ids=[case[0] for case in TEST_CASES],
)
def test_test_matches_jinja(name, value, args, expected):
    actual = TESTS[name](value, *args)
    assert actual == expected


# The tests of a `jinja2.Environment()`
JINJA_TESTS = (
    "!=", "<", "<=", "==", ">", ">=", "boolean", "callable", "defined", "divisibleby",
    "eq", "equalto", "escaped", "even", "false", "filter", "float", "ge", "greaterthan",
    "gt", "in", "integer", "iterable", "le", "lessthan", "lower", "lt", "mapping", "ne",
    "none", "number", "odd", "sameas", "sequence", "string", "test", "true", "undefined",
    "upper",
)


def test_every_jinja_test_is_present():
    assert set(JINJA_TESTS) <= set(TESTS)
