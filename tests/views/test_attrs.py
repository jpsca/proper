"""The `attrs` object of the components: its methods, one by one."""
import pytest

from proper.views import attrs as attrs_module
from proper.views.attrs import Attrs, check_name


def test_as_dict_str_and_repr():
    attrs = Attrs({"class": "a", "id": "x", "hidden": True})
    assert attrs.as_dict == {"class": "a", "id": "x", "hidden": True}
    assert str(attrs) == str(attrs.as_dict)
    assert repr(attrs) == f"Attrs({attrs.as_dict!r})"


def test_getitem_get_and_delitem():
    attrs = Attrs({"class": "a b", "data_id": 1, "hidden": True})
    assert attrs["class"] == "a b"
    assert attrs["classes"] == "a b"
    assert attrs["data_id"] == 1
    assert attrs.get("hidden") is True
    assert attrs.get("nope", "default") == "default"

    del attrs["hidden"]
    del attrs["data-id"]
    del attrs["class"]
    assert attrs.as_dict == {}


def test_set():
    attrs = Attrs({"id": "x", "hidden": True})
    attrs.set(id=None, hidden=False, classes="a", disabled=True, data_n=2)
    assert attrs.as_dict == {"class": "a", "data-n": 2, "disabled": True}


def test_setdefault():
    attrs = Attrs({"id": "x", "class": "a", "hidden": True})
    attrs.setdefault(id="y", classes="b", hidden=True, title=None, open=True, lang="es")
    assert attrs.as_dict == {"class": "a", "id": "x", "lang": "es", "hidden": True, "open": True}

    attrs = Attrs()
    attrs.setdefault(classes="b")
    assert attrs.classes == "b"


def test_classes():
    attrs = Attrs({"class": "a"})
    attrs.add_class("b c", "a")
    attrs.prepend_class("z", "b")
    attrs.remove_class("c")
    assert attrs.classes == "z a b"


def test_render():
    attrs = Attrs({"id": "x", "class": "a", "hidden": True})
    html = attrs.render(classes="first", id=None, hidden=False, open=True, title="t")
    assert html == 'class="first a" title="t" open'
    # render() doesn't change the attrs
    assert attrs.as_dict == {"class": "a", "id": "x", "hidden": True}


def test_render_only_properties_or_nothing():
    assert Attrs({"hidden": True}).render() == "hidden"
    assert Attrs().render() == ""
    assert Attrs({"x": None}).render(classes="") == ""


def test_repeated_classes_count_once():
    attrs = Attrs({"class": "a a", "classes": "b a"})
    assert attrs.classes == "a b"
    assert attrs.render(classes="b") == 'class="a b"'


def test_valid_names_kept_up_to_a_limit(monkeypatch):
    monkeypatch.setattr(attrs_module, "_VALID_NAMES", set())
    monkeypatch.setattr(attrs_module, "MAX_VALID_NAMES", 1)
    assert check_name("a") == "a"
    assert check_name("a") == "a"  # known
    assert check_name("b") == "b"
    assert attrs_module._VALID_NAMES == {"a"}
    with pytest.raises(ValueError):
        check_name("c d")
