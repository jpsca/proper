import pytest

from proper.support import Dot


def test_dict_init():
    dot = Dot({"a": 1, "B": 2, "foo": {"B": {"a": "r"}}})

    assert dot.a == 1
    assert dot.foo == {"B": {"a": "r"}}
    assert dot.foo.B.a == "r"


def test_iter_init():
    dot = Dot([("a", 1), ("B", 2), ("foo", {"B": {"a": "r"}})])

    assert dot.a == 1
    assert dot.foo == {"B": {"a": "r"}}
    assert dot.foo.B.a == "r"


def test_do_not_set_attributes():
    dot = Dot()

    with pytest.raises(AttributeError):
        dot.foo = "bar"


def test_can_set_underscore_attributes():
    dot = Dot()
    dot._foo = "bar"

    assert dot._foo == "bar"


def test_deep_update():
    dot = Dot(
        {
            "auth": {"hash": "sha1", "rounds": 123},
            "users": ["foo", "bar"],
            "a": 1,
            "foo": "bar",
        }
    )
    dot.update(
        {
            "auth": {"hash": "argon2"},
            "users": ["lorem", "ipsum"],
            "a": 2,
            "fizz": {"buzz": 3},
        }
    )

    assert dot == {
        "auth": {"hash": "argon2", "rounds": 123},
        "users": ["lorem", "ipsum"],
        "a": 2,
        "foo": "bar",
        "fizz": {"buzz": 3},
    }


def test_get():
    dot = Dot([("a", 1), ("B", 2), ("foo", {"B": {"a": "r"}})])

    assert dot.get("a") == 1
    assert dot.get("B") == 2
    assert dot.get("c", 99) == 99
    assert dot.get("d") is None
    assert dot.foo.get("B").get("a") == "r"
