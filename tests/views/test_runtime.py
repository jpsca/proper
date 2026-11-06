"""
Attribute and item lookup in the runtime, compared with Jinja's own
`Environment.getattr` / `Environment.getitem`.

What Jinja finds is fixed: each case has where Jinja 3.1.6 found the value
of `obj.name` and the one of `obj[name]`. It was recorded once, from the
tests that passed: each one is where the runtime found it too.
"""

from collections import OrderedDict, defaultdict
from types import SimpleNamespace

import pytest

from proper.views.runtime import getattr_, getitem, has_attr


# Where Jinja finds a value: in the attribute, in the item, or nowhere
ATTR = "attribute"
ITEM = "item"
MISSING = "missing"


class DictWithAttrs(dict):
    extra = "class attr"

    @property
    def name(self):
        return "property wins"


def cases():
    """The object, the name, and where Jinja finds `obj.name` and `obj[name]`."""
    d = {"name": "Ana", "items": "key named items", "get": "key named get", "__class__": "key", 1: "int key"}
    sub = DictWithAttrs(name="key", extra="key", other="other key")
    return [
        (d, "name", ITEM, ITEM),           # plain key: the shortcut
        (d, "items", ATTR, ITEM),          # dict attribute wins over the key, as in Jinja
        (d, "get", ATTR, ITEM),
        (d, "__class__", ATTR, ITEM),
        (d, "keys", ATTR, ATTR),           # attribute only
        (d, "missing", MISSING, MISSING),  # neither
        (d, 1, ITEM, ITEM),                # non-string name: goes to the key
        ({}, "name", MISSING, MISSING),
        (sub, "name", ATTR, ITEM),         # subclass property wins over the key
        (sub, "extra", ATTR, ITEM),        # subclass class attribute wins
        (sub, "other", ITEM, ITEM),        # subclass key
        (sub, "missing", MISSING, MISSING),
        (OrderedDict(a=1), "a", ITEM, ITEM),
        (OrderedDict(a=1), "keys", ATTR, ATTR),
        (SimpleNamespace(a=1), "a", ATTR, ATTR),
        (SimpleNamespace(a=1), "b", MISSING, MISSING),
        ([10, 20], 0, ITEM, ITEM),
        ("abc", "upper", ATTR, ATTR),
    ]


def found(obj, name, where):
    """The value that Jinja finds."""
    return getattr(obj, name) if where == ATTR else obj[name]


IDS = [f"{repr(obj)[:20]}-{repr(name)[:20]}" for obj, name, _, _ in cases()]


@pytest.mark.parametrize("obj,name,where,_", cases(), ids=IDS)
def test_getattr_matches_jinja(obj, name, where, _):
    # Jinja compiles `x.0` to a subscript, so it never calls getattr with a
    # number; the runtime's `getattr_` goes straight to the item for those.
    if where == MISSING:
        with pytest.raises(AttributeError):
            getattr_(obj, name)
        assert getattr_(obj, name, "dflt") == "dflt"
        assert has_attr(obj, name) is False
    else:
        assert getattr_(obj, name) == found(obj, name, where)
        assert has_attr(obj, name) is True


@pytest.mark.parametrize("obj,name,_,where", cases(), ids=IDS)
def test_getitem_matches_jinja(obj, name, _, where):
    if where == MISSING:
        with pytest.raises(AttributeError):
            getitem(obj, name)
    else:
        assert getitem(obj, name) == found(obj, name, where)


def test_none_value_is_found_not_missing():
    assert getattr_({"a": None}, "a", "dflt") is None
    assert has_attr({"a": None}, "a") is True


def test_defaultdict_takes_the_general_path():
    """Like Jinja, `d.x` on a defaultdict ends in `d["x"]`, which creates it."""
    d = defaultdict(list)
    assert getattr_(d, "x") == []
    assert "x" in d
