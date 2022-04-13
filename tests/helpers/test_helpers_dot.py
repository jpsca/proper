from proper.helpers import Dot


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


def test_dunder_attributes_is_not_key():
    dot = Dot()
    dot.__foo = "bar"

    assert dot.__foo == "bar"
    assert "__foo" not in dot


def test_deep_update():
    dot = Dot(
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
    dot = Dot([("a", 1), ("B", 2), ("foo", {"B": {"a": "r"}})])

    assert dot.get("a") == 1
    assert dot.get("B") == 2
    assert dot.get("c", 99) == 99
    assert dot.get("d") is None
    assert dot.foo.get("B").get("a") == "r"


def test_dicts_to_dots():
    dot = Dot()
    dot.a = 1
    dot.b = {}
    dot.b.c = 3
    assert dot.b.c == 3
