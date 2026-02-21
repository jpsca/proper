from proper.helpers import MultiDict


def test_get():
    md = MultiDict([("foo", "42"), ("foo", "16"), ("bar", "blub")])

    assert md.get("foo") == "16"
    assert md.get("foo", default="yay") == "16"
    assert md.get("foo", type=int) == 16
    assert md.get("foo", default=42, type=int) == 16
    assert md.get("foo", default="yay", type=int) == 16

    assert md.get("foo", index=0) == "42"

    assert md.get("bar") == "blub"
    assert md.get("bar", default="yay") == "blub"
    assert md.get("bar", type=int) is None
    assert md.get("bar", default=42, type=int) == 42
    assert md.get("bar", default="42", type=int) == "42"
    assert md.get("bar", default="yay", type=int) == "yay"

    assert md.get("meh") is None
    assert md.get("meh", default="yay") == "yay"
    assert md.get("meh", type=int) is None
    assert md.get("meh", default=42, type=int) == 42
    assert md.get("meh", default="42", type=int) == "42"
    assert md.get("meh", default="yay", type=int) == "yay"


def test_getall():
    md = MultiDict([
        ("foo", "42"),
        ("foo", "lorem"),
        ("foo", "16"),
        ("foo", "ipsum"),
        ("bar", "blub"),
        ("bar", "plop"),
        ("lorem", "ipsum"),
        ("lorem", "5"),
    ])
    assert md.getall("foo") == ["42", "lorem", "16", "ipsum"]
    assert md.getall("bar") == ["blub", "plop"]
    assert md.getall("lorem") == ["ipsum", "5"]
    assert md.getall("notfound") == []

    assert md.getall("foo", type=int) == [42, 16]
    assert md.getall("bar", type=int) == []
    assert md.getall("lorem", type=int) == [5]
    assert md.getall("notfound", type=int) == []


def test_init_from_dict():
    md = MultiDict({"a": 1, "b": 2})
    assert md.get("a") == 1
    assert md.get("b") == 2


def test_len():
    md = MultiDict([("a", 1), ("a", 2), ("b", 3)])
    assert len(md) == 2  # 2 distinct keys


def test_contains():
    md = MultiDict([("a", 1)])
    assert "a" in md
    assert "b" not in md


def test_iter():
    md = MultiDict([("a", 1), ("b", 2), ("a", 3)])
    assert set(md) == {"a", "b"}


def test_getitem():
    md = MultiDict([("a", 1), ("a", 2)])
    assert md["a"] == [1, 2]
    assert md["missing"] is None


def test_setitem_appends():
    md = MultiDict()
    md["a"] = 1
    md["a"] = 2
    assert md["a"] == [1, 2]


def test_delitem():
    md = MultiDict([("a", 1), ("b", 2)])
    del md["a"]
    assert "a" not in md
    assert "b" in md


def test_append():
    md = MultiDict()
    md.append("key", "v1")
    md.append("key", "v2")
    assert md.getall("key") == ["v1", "v2"]


def test_extend():
    md = MultiDict()
    md.extend("key", [1, 2, 3])
    assert md.getall("key") == [1, 2, 3]
    md.extend("key", [4])
    assert md.getall("key") == [1, 2, 3, 4]


def test_set_replaces():
    md = MultiDict([("a", 1), ("a", 2)])
    md.set("a", [99])
    assert md.getall("a") == [99]


def test_update_from_dict():
    md = MultiDict([("a", 1)])
    md.update({"a": 2, "b": 3})
    assert md.getall("a") == [1, 2]
    assert md.getall("b") == [3]


def test_update_from_iterable():
    md = MultiDict()
    md.update([("a", 1), ("a", 2), ("b", 3)])
    assert md.getall("a") == [1, 2]
    assert md.getall("b") == [3]


def test_update_from_multidict():
    md1 = MultiDict([("a", 1), ("a", 2)])
    md2 = MultiDict([("a", 3), ("b", 4)])
    md2.update(md1)
    assert md2.getall("a") == [3, 1, 2]
    assert md2.getall("b") == [4]


def test_keys():
    md = MultiDict([("a", 1), ("b", 2), ("a", 3)])
    assert set(md.keys()) == {"a", "b"}


def test_items():
    md = MultiDict([("a", 1), ("a", 2), ("b", 3)])
    items = dict(md.items())
    assert items["a"] == [1, 2]
    assert items["b"] == [3]


def test_repr():
    md = MultiDict([("a", 1)])
    assert "MultiDict" in repr(md)
