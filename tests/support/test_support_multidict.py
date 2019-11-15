from proper.support import exbool
from proper.support import MultiDict


def test_init():
    md = MultiDict(("foo", "42"), ("foo", "16"), ("bar", "blub"))
    assert md["foo"] == ["42", "16"]
    assert md["bar"] == ["blub"]


def test_get():
    md = MultiDict(("foo", "42"), ("foo", "16"), ("bar", "blub"))

    assert md.get("foo") == "16"
    assert md.get("foo", default="yay") == "16"
    assert md.get("foo", type=int) == 16
    assert md.get("foo", default=42, type=int) == 16
    assert md.get("foo", default="yay", type=int) == 16

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
    md = MultiDict(
        ("foo", "42"),
        ("foo", "lorem"),
        ("foo", "16"),
        ("foo", "ipsum"),
        ("bar", "blub"),
        ("bar", "plop"),
        ("lorem", "ipsum"),
        ("lorem", "5"),
    )
    assert md.getall("foo") == ["42", "lorem", "16", "ipsum"]
    assert md.getall("bar") == ["blub", "plop"]
    assert md.getall("lorem") == ["ipsum", "5"]
    assert md.getall("notfound") == []

    assert md.getall("foo", type=int) == [42, 16]
    assert md.getall("bar", type=int) == []
    assert md.getall("lorem", type=int) == [5]
    assert md.getall("notfound", type=int) == []


def test_exbool():
    md = MultiDict(
        ("false1", "off"),
        ("false1", "OfF"),
        ("false2", "0"),
        ("false3", "false"),
        ("false4", "False"),
        ("false5", "FALSE"),
        ("false6", "no"),
        ("false7", "NO"),

        ("true1", "yes"),
        ("true2", "YEAAAAAAAAH"),
        ("true3", "42"),
        ("true4", "affirmative"),
        ("true5", "whatever"),
    )

    assert not md.get("false1", type=exbool)
    assert not md.get("false1", type=exbool)
    assert not md.get("false2", type=exbool)
    assert not md.get("false3", type=exbool)
    assert not md.get("false4", type=exbool)
    assert not md.get("false5", type=exbool)
    assert not md.get("false6", type=exbool)
    assert not md.get("false7", type=exbool)

    assert md.get("true1", type=exbool)
    assert md.get("true2", type=exbool)
    assert md.get("true3", type=exbool)
    assert md.get("true4", type=exbool)
    assert md.get("true5", type=exbool)
