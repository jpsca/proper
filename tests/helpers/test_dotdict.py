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
    import pytest
    with pytest.raises(KeyError):
        _ = dot.nonexistent


def test_len():
    dot = DotDict({"a": 1, "b": 2, "c": 3})
    assert len(dot) == 3


def test_iter():
    dot = DotDict({"a": 1, "b": 2})
    assert set(dot) == {"a", "b"}


def test_equality_with_plain_dict():
    dot = DotDict({"a": 1, "b": {"c": 2}})
    assert dot == {"a": 1, "b": {"c": 2}}
