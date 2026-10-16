import pytest

from proper.helpers import DotDict


def test_dict_init():
    dot = DotDict({"a": 1, "B": 2, "foo": {"B": {"a": "r"}}})

    assert dot.a == 1
    assert dot.foo == {"B": {"a": "r"}}
    assert dot.foo.B.a == "r"


def test_iter_init():
    dot = DotDict([("a", 1), ("B", 2), ("foo", {"B": {"a": "r"}})])

    assert dot.a == 1
    assert dot.foo == {"B": {"a": "r"}}
    assert dot.foo.B.a == "r"


def test_dunder_attributes_is_not_key():
    dot = DotDict()
    dot.__foo = "bar"

    assert dot.__foo == "bar"
    assert "__foo" not in dot


def test_deep_update():
    dot = DotDict(
        {
            "auth": {"hash": "sha1", "rounds": 123},
            "users": ["foo", "bar"],
            "a": 1,
            "foo": "bar",
            "storage": {},
        }
    )
    dot.update(
        {
            "auth": {"hash": "argon2"},
            "users": ["lorem", "ipsum"],
            "a": 2,
            "fizz": {"buzz": 3},
            "storage": {"a": 1, "b": 2},
        }
    )

    print(dot)
    assert dot == {
        "auth": {"hash": "argon2", "rounds": 123},
        "users": ["lorem", "ipsum"],
        "a": 2,
        "foo": "bar",
        "fizz": {"buzz": 3},
        "storage": {"a": 1, "b": 2},
    }


def test_get():
    dot = DotDict([("a", 1), ("B", 2), ("foo", {"B": {"a": "r"}})])

    assert dot.get("a") == 1
    assert dot.get("B") == 2
    assert dot.get("c", 99) == 99
    assert dot.get("d") is None
    assert dot.foo.get("B").get("a") == "r"


def test_dicts_to_dots():
    dot = DotDict()
    dot.a = 1
    dot.b = {}
    dot.b.c = 3
    assert dot.b.c == 3


def test_setitem_converts_nested_dicts():
    dot = DotDict()
    dot["nested"] = {"a": {"b": 1}}
    assert isinstance(dot["nested"], DotDict)
    assert dot.nested.a.b == 1


def test_contains():
    dot = DotDict({"a": 1, "b": 2})
    assert "a" in dot
    assert "c" not in dot


def test_delitem():
    dot = DotDict({"a": 1, "b": 2})
    del dot["a"]
    assert "a" not in dot
    assert "b" in dot


def test_copy():
    dot = DotDict({"a": 1, "nested": {"b": 2}})
    copied = dot.copy()

    assert copied == dot
    assert isinstance(copied, DotDict)
    assert isinstance(copied.nested, DotDict)

    copied.a = 99
    assert dot.a == 1


def test_kwargs_init():
    dot = DotDict(x=1, y=2)
    assert dot.x == 1
    assert dot.y == 2


def test_deep_update_three_levels():
    dot = DotDict({"a": {"b": {"c": 1, "d": 2}}})
    dot.update({"a": {"b": {"c": 99}}})
    assert dot.a.b.c == 99
    assert dot.a.b.d == 2


def test_deep_update_new_key_deep_copied():
    original = {"inner": [1, 2, 3]}
    dot = DotDict()
    dot.update({"key": original})

    original["inner"].append(4)
    assert dot.key.inner == [1, 2, 3]


def test_missing_key_raises():
    dot = DotDict({"a": 1})

    with pytest.raises(AttributeError):
        _ = dot.nonexistent

    # hasattr and getattr with default should work correctly
    assert not hasattr(dot, "nonexistent")
    assert getattr(dot, "nonexistent", "default") == "default"

    # KeyError still raised for dict-style access
    with pytest.raises(KeyError):
        _ = dot["nonexistent"]


def test_len():
    dot = DotDict({"a": 1, "b": 2, "c": 3})
    assert len(dot) == 3


def test_iter():
    dot = DotDict({"a": 1, "b": 2})
    assert set(dot) == {"a", "b"}


def test_equality_with_plain_dict():
    dot = DotDict({"a": 1, "b": {"c": 2}})
    assert dot == {"a": 1, "b": {"c": 2}}


class Slow(DotDict):
    """A subclass: built with `update()`, the general case."""


SOURCES = [
    {},
    {"a": 1, "b": "x", "c": None, "d": 1.5, "e": True, "f": b"raw"},
    {"user": {"id": 1, "roles": ["admin"], "prefs": {"lang": "es"}}},
    {"cart": [1, {"sku": "a"}], "tags": ("x", "y"), "seen": {1, 2}},
    {"deep": {"list": [{"x": 1}], "set": {3}}},
]


def as_plain(value):
    """The structure, with each mapping's type: `DotDict` and `Slow` are the same."""
    if isinstance(value, dict):
        return ("dotdict" if isinstance(value, DotDict) else "dict",
                {k: as_plain(v) for k, v in value.items()})
    if isinstance(value, list):
        return [as_plain(v) for v in value]
    return value


@pytest.mark.parametrize("src", SOURCES)
def test_built_from_a_dict_as_update_builds_it(src):
    assert as_plain(DotDict(src)) == as_plain(Slow(src))


@pytest.mark.parametrize("src", SOURCES)
def test_copy_as_update_copies(src):
    assert as_plain(DotDict(src).copy()) == as_plain(Slow(src).copy())
    assert type(DotDict(src).copy()) is DotDict
    assert type(Slow(src).copy()) is Slow


def test_what_is_copied():
    """Like `update()`: the dicts are copied deep; at the top, the other
    values are copied one level; inside a dict, deep."""
    src = {"top": [{"x": 1}], "nested": {"inner": [{"y": 1}]}}
    for dot in (DotDict(src), DotDict(src).copy(), Slow(src)):
        dot.top.append(2)
        dot.nested.inner[0]["y"] = 2
        dot.top[0]["x"] = 3
    assert src["top"] == [{"x": 3}]  # one level: the dict inside is shared
    assert src["nested"] == {"inner": [{"y": 1}]}  # deep: nothing shared


def test_a_copy_does_not_share_with_the_original():
    dot = DotDict({"a": {"b": [1]}, "c": [1]})
    other = dot.copy()
    other.a.b.append(2)
    other.c.append(2)
    other.a.new = 1
    assert dot == {"a": {"b": [1]}, "c": [1]}


def test_kwargs_and_pairs_still_take_the_general_way():
    assert DotDict({"a": {"b": 1}}, c=2) == {"a": {"b": 1}, "c": 2}
    assert DotDict([("a", {"b": 1})]).a.b == 1
