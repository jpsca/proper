"""
Jx | Copyright (c) Juan-Pablo Scaletti

Structural errors. The regex parser could not see any of these: it matched
opening tags and searched forward for a closing one, so it had no idea whether
a `{% if %}` block sat across the boundary.
"""

import pytest

from proper.jx import parse_ast
from proper.jx.exceptions import TemplateSyntaxError
from proper.jx.nodes import Component, Document, Fill, Slot


def parse(source: str, components=None):
    return parse_ast(source, name="test", components=components)


def position_of(source: str, components=None) -> tuple[int, int]:
    """Parse and return the (line, col) reported in the error."""
    with pytest.raises(TemplateSyntaxError) as info:
        parse(source, components)
    header = str(info.value).split("\n")[0]
    inside = header[header.index("[") + 1 : header.index("]")]
    _, line, col = inside.rsplit(":", 2)
    return int(line), int(col)


# --- structure --------------------------------------------------------------


def test_component_not_closed_inside_its_block():
    """Opened inside the `{% if %}`, still open when the block ends."""
    with pytest.raises(TemplateSyntaxError, match="not closed inside"):
        parse("{% if x %}<Card>{% endif %}</Card>")


def test_component_closed_outside_its_block():
    """Opened outside the `{% if %}`, closed from inside it."""
    with pytest.raises(TemplateSyntaxError, match="closed outside the block"):
        parse("<Card>{% if x %}</Card>{% endif %}")


def test_unclosed_component():
    with pytest.raises(TemplateSyntaxError, match="Unclosed component `Card`"):
        parse("<Card>never closed")


def test_unclosed_nested_component():
    with pytest.raises(TemplateSyntaxError, match="Unclosed component `Card`"):
        parse("<Card><Card>a</Card>")


def test_unclosed_slot():
    with pytest.raises(TemplateSyntaxError, match=r"Unclosed `\{% slot header %\}`"):
        parse("{% slot header %}no end")


def test_unclosed_fill():
    with pytest.raises(TemplateSyntaxError, match=r"Unclosed `\{% fill header %\}`"):
        parse("<Card>{% fill header %}no end</Card>")


def test_unclosed_jinja_block():
    with pytest.raises(TemplateSyntaxError, match=r"Unclosed `\{% for %\}`"):
        parse("{% for x in y %}nope")


def test_fill_must_be_directly_inside_a_component():
    with pytest.raises(TemplateSyntaxError, match="must be directly inside"):
        parse("{% fill header %}x{% endfill %}")


def test_fill_inside_a_loop_inside_a_component_is_rejected():
    """
    The regex parser hoisted this fill out of its loop, silently losing the
    loop variable. There is no correct place to put it, so it is an error.
    """
    with pytest.raises(TemplateSyntaxError, match="must be directly inside"):
        parse("<Card>{% for i in x %}{% fill a %}{{ i }}{% endfill %}{% endfor %}</Card>")


def test_slot_needs_a_name():
    with pytest.raises(TemplateSyntaxError, match="needs a name"):
        parse("{% slot %}x{% endslot %}")


def test_slot_rejects_anything_after_the_name():
    """A name is all a slot takes; a typo used to be dropped without a word."""
    with pytest.raises(TemplateSyntaxError, match="Unexpected `typo`"):
        parse("{% slot header typo %}x{% endslot %}")


def test_fill_rejects_anything_after_the_name():
    with pytest.raises(TemplateSyntaxError, match="Unexpected `typo`"):
        parse("<Card>{% fill header typo %}x{% endfill %}</Card>")


@pytest.mark.parametrize(
    "source, message",
    [
        # The end tags take nothing at all.
        ("{% slot a %}x{% endslot typo %}", "Unexpected `typo`"),
        ("<Card>{% fill a %}x{% endfill typo %}</Card>", "Unexpected `typo`"),
        # The keyword has to be separated from the name, or this reads as a
        # slot named `-header` instead of the typo it is.
        ("{% slot-header %}x{% endslot %}", "needs a name"),
        ("<Card>{% fill.header %}x{% endfill %}</Card>", "needs a name"),
    ],
)
def test_malformed_slot_constructs_are_rejected(source, message):
    with pytest.raises(TemplateSyntaxError, match=message):
        parse(source, components=["Card"])


@pytest.mark.parametrize(
    "source",
    [
        "{% slot header %}x{% endslot %}",
        "{% slot header %}x{% endslot -%}",
        "{% slot header %}x{% endslot +%}",
        "<Card>{% fill header %}x{% endfill -%}</Card>",
        "{% slot header -%}x{%- endslot %}",
        # `+` is a marker too, not trailing text.
        "{% slot header +%}x{%+ endslot %}",
        "{%+ slot header +%}x{%- endslot -%}",
        "<Card>{% fill header +%}x{% endfill %}</Card>",
        "<Card>{% fill header -%}x{%- endfill %}</Card>",
    ],
)
def test_whitespace_control_after_the_name_is_not_trailing_text(source):
    parse(source)


def test_stray_closing_tag_is_an_error():
    with pytest.raises(TemplateSyntaxError, match="no component is open"):
        parse("</Card>")


def test_closing_tag_that_does_not_match_the_open_one():
    with pytest.raises(
        TemplateSyntaxError, match=r"Unexpected `</Card>`, the open component is `Box`"
    ):
        parse("<Box></Card>")


def test_closing_a_component_twice():
    with pytest.raises(TemplateSyntaxError, match="no component is open"):
        parse("<Card>a</Card></Card>")


def test_closing_a_self_closed_component():
    with pytest.raises(TemplateSyntaxError, match="no component is open"):
        parse("<Card />a</Card>")


def test_unknown_block_tags_pass_through():
    """A block from a user extension is not something we can pair up."""
    document = parse("{% cache 60 %}x{% endcache %}")
    assert len(document.children) == 3


# --- positions --------------------------------------------------------------


@pytest.mark.parametrize(
    "source, expected",
    [
        ("<Card>", (1, 0)),
        ("\n\n  <Card>", (3, 2)),
        ('<Valid\n  a="1"\n  b="2"\n/>\n<Card>', (5, 0)),
        ("{{ x }}\n{# c #}\n<Card>", (3, 0)),
        ("{% raw %}\n<Card>\n{% endraw %}\n<Card>", (4, 0)),
        ("ñandú 日本語 <Card>", (1, 10)),
    ],
)
def test_error_position(source, expected):
    assert position_of(source, ["Valid", "Card"]) == expected


def test_caret_points_at_the_column():
    with pytest.raises(TemplateSyntaxError) as info:
        parse("  <Nope />", components=["Card"])
    line, caret = str(info.value).split("\n")[1:3]
    assert caret.index("^") == line.index("<Nope")


# --- the tree ---------------------------------------------------------------


def test_tree_shape():
    document = parse(
        '<Card a="1">{% fill head %}H{% endfill %}main</Card>', components=["Card"]
    )
    assert isinstance(document, Document)
    card = document.children[0]
    assert isinstance(card, Component)
    assert card.name == "Card"
    assert [a.name for a in card.attrs] == ["a"]
    assert [f.name for f in card.fills] == ["head"]
    assert isinstance(card.fills[0], Fill)
    assert card.children[0].value == "main"


def test_tags_inside_comments_and_raw_are_not_components():
    document = parse("{# <Card /> #}{% raw %}<Card />{% endraw %}")
    assert not [n for n in _all(document) if isinstance(n, Component)]


def test_slots_are_found_anywhere():
    document = parse("<Card>{% slot a %}{% endslot %}</Card>", components=["Card"])
    slots = [n for n in _all(document) if isinstance(n, Slot)]
    assert [s.name for s in slots] == ["a"]


def _all(node):
    from proper.jx import walk

    return walk(node)
