"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import pytest

from proper.jx.exceptions import TemplateSyntaxError
from proper.jx.lexer import AttrKind, Lexer, TokenType


def kinds(source: str) -> list[str]:
    return [token.type.value for token in Lexer("t", source).tokens()]


def only(source: str):
    tokens = Lexer("t", source).tokens()
    assert len(tokens) == 1, [t.type.value for t in tokens]
    return tokens[0]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("", []),
        ("plain text", ["text"]),
        ("a < b and c > d", ["text"]),
        ("<div>x</div>", ["text"]),
        ("{{ x }}", ["expr"]),
        ("{% if x %}{% endif %}", ["stmt", "stmt"]),
        # `+` means "keep the whitespace", and has to be stepped over just like
        # `-`, or the keyword comes out empty and the tag is not recognized.
        ("{%+ if x %}{%+ endif %}", ["stmt", "stmt"]),
        ("{%- if x -%}{%- endif -%}", ["stmt", "stmt"]),
        ("{# c #}", ["comment"]),
        ("{% raw %}{{ x }}<Card />{% endraw %}", ["raw"]),
        # Nothing inside a raw block is scanned, so a bare `{%` is just text.
        ("{% raw %}Use {% in a sentence{% endraw %}", ["raw"]),
        ("""{% raw %}{% "unterminated quote{% endraw %}""", ["raw"]),
        # Every spelling of the terminator Jinja accepts.
        ("{% raw %}a{%endraw%}", ["raw"]),
        ("{% raw %}a{%- endraw %}", ["raw"]),
        ("{% raw %}a{%+ endraw %}", ["raw"]),
        ("{% raw %}a{% endraw -%}", ["raw"]),
        # The first terminator wins: raw blocks do not nest.
        ("{% raw %}{% raw %}{% endraw %}x", ["raw", "text"]),
        ("<Card />", ["tag_open"]),
        ("<Card>x</Card>", ["tag_open", "text", "tag_close"]),
        ("a{{ b }}c", ["text", "expr", "text"]),
        ("Use <hr in a sentence", ["text"]),
        ("a <3 b", ["text"]),
        ("</Card>", ["tag_close"]),
    ],
)
def test_token_kinds(source, expected):
    assert kinds(source) == expected


@pytest.mark.parametrize(
    "source, value",
    [
        ("{{ x }}", "{{ x }}"),
        ("{{ 'a}}b' }}", "{{ 'a}}b' }}"),
        ('{{ "a}}b" }}', '{{ "a}}b" }}'),
        ("{{ {'a': 1} }}", "{{ {'a': 1} }}"),
        # The regex parser stopped at the first `}}` and left a stray brace.
        ("{{ {'a':1}}}", "{{ {'a':1}}}"),
        ("{{ d['x'] }}", "{{ d['x'] }}"),
        ("{{ f(g(1)) }}", "{{ f(g(1)) }}"),
        (r"{{ 'it\'s' }}", r"{{ 'it\'s' }}"),
    ],
)
def test_expression_boundaries(source, value):
    token = only(source)
    assert token.type is TokenType.EXPR
    assert token.value == value


def test_attributes():
    token = only('<Card a="1" b=\'2\' c={{ x + 1 }} flag data-id="9" />')
    assert token.self_closing is True
    got = [(a.name, a.value, a.kind) for a in token.attrs]
    assert got == [
        ("a", '"1"', AttrKind.STRING),
        ("b", "'2'", AttrKind.STRING),
        ("c", "{{ x + 1 }}", AttrKind.EXPR),
        ("flag", None, AttrKind.FLAG),
        ("data-id", '"9"', AttrKind.STRING),
    ]


def test_attribute_names_keep_their_source_spelling():
    """Normalizing `-` to `_` is the emitter's job, not the lexer's."""
    token = only('<Card data-foo="1" />')
    assert token.attrs[0].name == "data-foo"


@pytest.mark.parametrize(
    "source",
    [
        '<Card label="a > b" />',
        "<Card label='a > b' />",
        '<Card label="{{ x if y else \'a>b\' }}" />',
        r'<Card label="say \"hi\"" />',
    ],
)
def test_a_gt_inside_a_value_does_not_end_the_tag(source):
    token = only(source)
    assert token.self_closing is True
    assert len(token.attrs) == 1


@pytest.mark.parametrize(
    "source, keyword, lstrip, rstrip",
    [
        ("{% if x %}", "if", False, False),
        ("{%- if x -%}", "if", True, True),
        ("{%+ if x +%}", "if", False, False),
        ("{%- if x +%}", "if", True, False),
        ("{%+ if x -%}", "if", False, True),
    ],
)
def test_whitespace_control_markers(source, keyword, lstrip, rstrip):
    token = only(source)
    assert (token.name, token.lstrip, token.rstrip) == (keyword, lstrip, rstrip)


def test_positions_are_tracked():
    tokens = Lexer("t", "line one\nline two <Card />\n").tokens()
    tag = next(t for t in tokens if t.type is TokenType.TAG_OPEN)
    assert (tag.span.line, tag.span.col) == (2, 9)


def test_positions_after_a_multiline_tag():
    source = '<Card\n  a="1"\n  b="2"\n/>\n<Other />'
    tokens = Lexer("t", source).tokens()
    other = [t for t in tokens if t.type is TokenType.TAG_OPEN][1]
    assert (other.span.line, other.span.col) == (5, 0)


@pytest.mark.parametrize(
    "source, message",
    [
        ("{{ oops", "Unclosed expression"),
        ("{# oops", "Unclosed comment"),
        ("{% oops", "Unclosed statement"),
        ("{% raw %}oops", "Unclosed '{% raw %}'"),
        ('<Card a="oops />', "Syntax error"),
        # An uppercase word after `<` starts a tag, so it must be closed.
        ("Use <Hr in a sentence", "Syntax error"),
        ("<Card a={{ oops />", "Syntax error"),
        ("<Card a={{ {{ x }} />", "Unmatched braces"),
        ("<Card a=bare />", "must be quoted"),
        ('<Card a="1" a="2" />', "Duplicate attribute"),
        # `data-id` and `data_id` both reach the template as `data_id`.
        ('<Card data-id="1" data_id="2" />', "Duplicate attribute"),
    ],
)
def test_lexer_errors(source, message):
    with pytest.raises(TemplateSyntaxError, match=message):
        Lexer("t", source).tokens()
