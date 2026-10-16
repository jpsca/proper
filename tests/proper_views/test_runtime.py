"""
Attribute and item lookup in the runtime, compared with Jinja's own
`Environment.getattr` / `Environment.getitem`.
"""

from collections import OrderedDict, defaultdict
from types import SimpleNamespace

import jinja2
import pytest

from proper.views.runtime import getattr_, getitem, has_attr


ENV = jinja2.Environment()


class DictWithAttrs(dict):
    extra = "class attr"

    @property
    def name(self):
        return "property wins"


def cases():
    d = {"name": "Ana", "items": "key named items", "get": "key named get", "__class__": "key", 1: "int key"}
    sub = DictWithAttrs(name="key", extra="key", other="other key")
    return [
        (d, "name"),              # plain key: the shortcut
        (d, "items"),             # dict attribute wins over the key, as in Jinja
        (d, "get"),
        (d, "__class__"),
        (d, "keys"),              # attribute only
        (d, "missing"),           # neither
        (d, 1),                   # non-string name: goes to the key
        ({}, "name"),
        (sub, "name"),            # subclass property wins over the key
        (sub, "extra"),           # subclass class attribute wins
        (sub, "other"),           # subclass key
        (sub, "missing"),
        (OrderedDict(a=1), "a"),
        (OrderedDict(a=1), "keys"),
        (SimpleNamespace(a=1), "a"),
        (SimpleNamespace(a=1), "b"),
        ([10, 20], 0),
        ("abc", "upper"),
    ]


def jinja_value(fn, obj, name):
    value = fn(obj, name)
    return None if isinstance(value, jinja2.Undefined) else ("ok", value)


@pytest.mark.parametrize("obj,name", cases(), ids=lambda x: repr(x)[:20])
def test_getattr_matches_jinja(obj, name):
    # Jinja compiles `x.0` to a subscript, so it never calls getattr with a
    # number; minijx's `getattr_` goes straight to the item for those.
    lookup = ENV.getattr if isinstance(name, str) else ENV.getitem
    expected = jinja_value(lookup, obj, name)
    if expected is None:
        with pytest.raises(AttributeError):
            getattr_(obj, name)
        assert getattr_(obj, name, "dflt") == "dflt"
        assert has_attr(obj, name) is False
    else:
        assert getattr_(obj, name) == expected[1]
        assert has_attr(obj, name) is True


@pytest.mark.parametrize("obj,name", cases(), ids=lambda x: repr(x)[:20])
def test_getitem_matches_jinja(obj, name):
    expected = jinja_value(ENV.getitem, obj, name)
    if expected is None:
        with pytest.raises(AttributeError):
            getitem(obj, name)
    else:
        assert getitem(obj, name) == expected[1]


def test_none_value_is_found_not_missing():
    assert getattr_({"a": None}, "a", "dflt") is None
    assert has_attr({"a": None}, "a") is True


def test_defaultdict_takes_the_general_path():
    """Like Jinja, `d.x` on a defaultdict ends in `d["x"]`, which creates it."""
    d = defaultdict(list)
    assert getattr_(d, "x") == jinja_value(ENV.getattr, defaultdict(list), "x")[1] == []
    assert "x" in d
