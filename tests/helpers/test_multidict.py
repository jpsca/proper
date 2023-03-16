from proper.helpers import MultiDict


def test_init():
    md = MultiDict([("foo", "42"), ("foo", "16"), ("bar", "blub")])
    assert md["foo"] == ["42", "16"]
    assert md["bar"] == ["blub"]


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
