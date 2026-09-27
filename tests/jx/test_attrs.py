"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import pytest
from markupsafe import Markup

from proper.jx.attrs import Attrs


def test_parse_initial_attrs():
    attrs = Attrs(
        {
            "title": "hi",
            "data-position": "top",
            "class": "z4 c3 a1 z4 b2",
            "open": True,
            "disabled": False,
            "value": 0,
            "foobar": None,
            "_content": "content",
        }
    )
    assert attrs.classes == "z4 c3 a1 b2"
    assert attrs.get("class") == "z4 c3 a1 b2"
    assert attrs.get("data-position") == "top"
    assert attrs.get("data_position") == "top"
    assert attrs.get("title") == "hi"
    assert attrs.get("open") is True
    assert attrs.get("disabled", "meh") == "meh"
    assert attrs.get("value") == "0"

    assert attrs.get("disabled") is None
    assert attrs.get("foobar") is None

    attrs.set(data_value=0)
    attrs.set(data_position=False)
    assert attrs.get("data-value") == "0"
    assert attrs.get("data-position") is None
    assert attrs.get("data_position") is None


def test_getattr():
    attrs = Attrs(
        {
            "title": "hi",
            "class": "z4 c3 a1 z4 b2",
            "open": True,
        }
    )
    assert attrs["class"] == "z4 c3 a1 b2"
    assert attrs["title"] == "hi"
    assert attrs["open"] is True
    assert attrs["lorem"] is None


def test_deltattr():
    attrs = Attrs(
        {
            "title": "hi",
            "class": "z4 c3 a1 z4 b2",
            "open": True,
        }
    )
    assert attrs["class"] == "z4 c3 a1 b2"
    del attrs["title"]
    assert attrs["title"] is None


def test_render():
    attrs = Attrs(
        {
            "title": "hi",
            "data-position": "top",
            "class": "z4 c3 a1 z4 b2",
            "open": True,
            "disabled": False,
        }
    )
    assert 'class="z4 c3 a1 b2" data-position="top" title="hi" open' == attrs.render()


def test_set():
    attrs = Attrs({})
    attrs.set(title="hi", data_position="top")
    attrs.set(open=True)
    assert 'data-position="top" title="hi" open' == attrs.render()

    attrs.set(title=False, open=False)
    assert 'data-position="top"' == attrs.render()


def test_class_management():
    attrs = Attrs(
        {
            "class": "z4 c3  a1  z4  b2",
        }
    )
    attrs.set(classes="lorem bipsum lorem a1")

    assert attrs.classes == "z4 c3 a1 b2 lorem bipsum"

    attrs.remove_class("lorem")
    assert attrs.classes == "z4 c3 a1 b2 bipsum"

    attrs.prepend_class("button |", "wat")
    assert attrs.classes == "button | wat z4 c3 a1 b2 bipsum"

    attrs.set(classes=None)
    attrs.set(classes="meh")
    assert attrs.classes == "meh"


def test_setdefault():
    attrs = Attrs(
        {
            "title": "hi",
        }
    )
    attrs.setdefault(
        title="default title",
        data_lorem="ipsum",
        open=True,
        disabled=False,
    )
    assert 'data-lorem="ipsum" title="hi" open' == attrs.render()


def test_setdefault_property_already_present():
    attrs = Attrs(
        {
            "open": True,
        }
    )
    attrs.setdefault(open=True, hidden=True)
    assert "hidden open" == attrs.render()


def test_setdefault_classes():
    attrs = Attrs({"class": "a"})
    attrs.setdefault(classes="a b c")
    assert 'class="a"' == attrs.render()

    attrs = Attrs({})
    attrs.setdefault(classes="a b c")
    assert 'class="a b c"' == attrs.render()


def test_as_dict():
    attrs = Attrs(
        {
            "title": "hi",
            "data-position": "top",
            "class": "z4 c3 a1 z4 b2",
            "open": True,
            "disabled": False,
        }
    )
    assert attrs.as_dict == {
        "class": "z4 c3 a1 b2",
        "data-position": "top",
        "title": "hi",
        "open": True,
    }


def test_as_dict_no_classes():
    attrs = Attrs(
        {
            "title": "hi",
            "data-position": "top",
            "open": True,
        }
    )
    assert attrs.as_dict == {
        "data-position": "top",
        "title": "hi",
        "open": True,
    }


def test_render_attrs_lik_set():
    attrs = Attrs({"class": "lorem"})
    expected = 'class="ipsum lorem" data-position="top" title="hi" open'
    result = attrs.render(
        title="hi",
        data_position="top",
        classes="ipsum",
        open=True,
    )
    print(result)
    assert expected == result


def test_escape_tailwind_syntax():
    # The `&` is escaped, but the browser decodes it back while parsing, so the
    # class lands in the DOM as `[&_a]:flex` and Tailwind's selector still matches.
    attrs = Attrs({"class": "lorem [&_a]:flex"})
    expected = 'class="ipsum lorem [&amp;_a]:flex" title="Hi&amp;Stuff"'
    result = attrs.render(
        **{
            "title": "Hi&Stuff",
            "class": "ipsum",
        }
    )
    print(result)
    assert expected == result


def test_do_escape_quotes_inside_attrs():
    attrs = Attrs(
        {
            "class": "lorem text-['red']",
            "title": """I said "Hey O'Neill, what's up?" to him""",
            "data-dim": '14"3',
            "open": True,
        }
    )
    expected = """class="lorem text-['red']" data-dim='14"3' title="I said &quot;Hey O'Neill, what's up?&quot; to him" open"""
    result = attrs.render()
    print(result)
    assert expected == result


def test_additional_attributes_are_lazily_evaluated_to_strings():
    class TestObject:
        def __str__(self):
            raise RuntimeError("Should not be called unless rendered.")

    attrs = Attrs(
        {
            "some_object": TestObject(),
        }
    )

    with pytest.raises(RuntimeError):
        attrs.render()


def test_additional_attributes_lazily_evaluated_has_string_methods():
    class TestObject:
        def __str__(self):
            return "test"

    attrs = Attrs({"some_object": TestObject()})

    assert attrs["some_object"].__str__
    assert attrs["some_object"].__repr__
    assert attrs["some_object"].__int__
    assert attrs["some_object"].__float__
    assert attrs["some_object"].__complex__
    assert attrs["some_object"].__hash__
    assert attrs["some_object"].__eq__
    assert attrs["some_object"].__lt__
    assert attrs["some_object"].__le__
    assert attrs["some_object"].__gt__
    assert attrs["some_object"].__ge__
    assert attrs["some_object"].__contains__
    assert attrs["some_object"].__len__
    assert attrs["some_object"].__getitem__
    assert attrs["some_object"].__add__
    assert attrs["some_object"].__radd__
    assert attrs["some_object"].__mul__
    assert attrs["some_object"].__mod__
    assert attrs["some_object"].__rmod__
    assert attrs["some_object"].capitalize
    assert attrs["some_object"].casefold
    assert attrs["some_object"].center
    assert attrs["some_object"].count
    assert attrs["some_object"].removeprefix
    assert attrs["some_object"].removesuffix
    assert attrs["some_object"].encode
    assert attrs["some_object"].endswith
    assert attrs["some_object"].expandtabs
    assert attrs["some_object"].find
    assert attrs["some_object"].format
    assert attrs["some_object"].format_map
    assert attrs["some_object"].index
    assert attrs["some_object"].isalpha
    assert attrs["some_object"].isalnum
    assert attrs["some_object"].isascii
    assert attrs["some_object"].isdecimal
    assert attrs["some_object"].isdigit
    assert attrs["some_object"].isidentifier
    assert attrs["some_object"].islower
    assert attrs["some_object"].isnumeric
    assert attrs["some_object"].isprintable
    assert attrs["some_object"].isspace
    assert attrs["some_object"].istitle
    assert attrs["some_object"].isupper
    assert attrs["some_object"].join
    assert attrs["some_object"].ljust
    assert attrs["some_object"].lower
    assert attrs["some_object"].lstrip
    assert attrs["some_object"].partition
    assert attrs["some_object"].replace
    assert attrs["some_object"].rfind
    assert attrs["some_object"].rindex
    assert attrs["some_object"].rjust
    assert attrs["some_object"].rpartition
    assert attrs["some_object"].rstrip
    assert attrs["some_object"].split
    assert attrs["some_object"].rsplit
    assert attrs["some_object"].splitlines
    assert attrs["some_object"].startswith
    assert attrs["some_object"].strip
    assert attrs["some_object"].swapcase
    assert attrs["some_object"].title
    assert attrs["some_object"].translate
    assert attrs["some_object"].upper
    assert attrs["some_object"].zfill

    assert attrs["some_object"].upper() == "TEST"
    assert attrs["some_object"].title() == "Test"


def test_render_empty_attrs():
    """Render with no attributes, classes, or properties returns empty string."""
    attrs = Attrs({})
    assert attrs.render() == ""


def test_render_does_not_mutate_self():
    """Calling render() with kw args must not change the Attrs instance."""
    attrs = Attrs({"class": "original", "id": "x"})
    result1 = attrs.render(classes="extra", title="hi")
    assert 'class="extra original"' in result1
    assert 'title="hi"' in result1

    # Second call should produce the same result — no accumulated state
    result2 = attrs.render(classes="extra", title="hi")
    assert result1 == result2

    # The original attrs should be unchanged
    assert attrs.classes == "original"
    assert attrs.get("title") is None


def test_render_kw_removes_attrs_without_mutating():
    """Passing False in render kw removes from the copy, not from self."""
    attrs = Attrs({"title": "hi", "open": True})
    result = attrs.render(title=False, open=False)
    assert result == ""

    # Original attrs unchanged
    assert attrs.get("title") is not None
    assert attrs.get("open") is True


def test_render_with_kw_no_classes():
    """Render with kw args that don't include class keys."""
    attrs = Attrs({})
    result = attrs.render(title="hi", open=True)
    assert 'title="hi"' in result
    assert "open" in result


def test_prepend_class_dedupes_within_its_own_arguments():
    attrs = Attrs({"class": "a"})
    attrs.prepend_class("d d", "e", "d e")
    assert attrs.classes == "d e a"


def test_do_escape_entities_inside_attrs():
    attrs = Attrs(
        {
            "href": "/search?a=1&b=2",
            "title": "a < b & c",
            "data-raw": "&amp;",
        }
    )
    expected = (
        'data-raw="&amp;amp;" href="/search?a=1&amp;b=2" title="a &lt; b &amp; c"'
    )
    assert attrs.render() == expected


def test_escaped_entities_do_not_break_quote_switching():
    # `&` is escaped before `"` becomes `&quot;`, so the entity is not double-escaped.
    attrs = Attrs({"title": """B&B said "hi" to O'Neill"""})
    assert attrs.render() == 'title="B&amp;B said &quot;hi&quot; to O\'Neill"'


def test_markup_values_are_not_double_escaped():
    attrs = Attrs(
        {
            "href": Markup("/s?a=1&amp;b=2"),
            "title": Markup("a&nbsp;b"),
            "data-plain": "/s?a=1&b=2",
        }
    )
    assert attrs.render() == (
        'data-plain="/s?a=1&amp;b=2" href="/s?a=1&amp;b=2" title="a&nbsp;b"'
    )


def test_markup_values_survive_render_kwargs():
    assert Attrs({}).render(href=Markup("/s?a=1&amp;b=2")) == 'href="/s?a=1&amp;b=2"'


def test_attrs_does_not_mutate_the_dict_it_is_given():
    source = {"class": "a b", "classes": "c", "id": "x"}

    first = Attrs(source)
    assert source == {"class": "a b", "classes": "c", "id": "x"}

    # Reusing the same dict must give the same result, not one stripped of classes.
    second = Attrs(source)
    assert first.render() == second.render() == 'class="a b c" id="x"'
