"""
Jx | Copyright (c) Juan-Pablo Scaletti

The `{# def #}` / `{# import #}` / `{# css #}` / `{# js #}` header, scanned by
the lexer instead of matched with regular expressions.
"""

import pytest

from proper.jx import parse_ast
from proper.jx.lexer import scan_header, split_declaration, strip_inline_comments


def keywords(source: str) -> list[tuple[str, str]]:
    return [(kw, expr) for kw, expr, *_ in scan_header(source)]


# --- what counts as the header ----------------------------------------------


def test_header_stops_at_the_first_real_content():
    source = '{# def a #}\n<div />\n{# css "late.css" #}'
    assert keywords(source) == [("def", "a")]


def test_plain_comments_do_not_end_the_header():
    source = "{# just a note #}\n{# def a #}\n<div />"
    assert keywords(source) == [("def", "a")]


def test_whitespace_between_declarations_is_allowed():
    source = '\n\n  {# def a #}\n\n  {# js "x.js" #}\n<div />'
    assert keywords(source) == [("def", "a"), ("js", '"x.js"')]


def test_a_body_that_does_not_lex_still_has_a_readable_header():
    """
    `jx check` reads the metadata before parsing, so a broken body must not
    stop it from finding out which components the file imports.
    """
    source = '{# import "card.jx" as Card #}\n<Card a=bare>'
    assert keywords(source) == [("import", '"card.jx" as Card')]


def test_unclosed_header_comment_yields_nothing():
    assert keywords("{# def a\n<div />") == []


# --- splitting one declaration ----------------------------------------------


@pytest.mark.parametrize(
    "comment, expected",
    [
        ("{# def a #}", ("def", "a")),
        ("{#def a#}", ("def", "a")),
        ("{#- def a -#}", ("def", "a")),
        ("{#   def   a, b=1   #}", ("def", "a, b=1")),
        ('{# import "a.jx" as A #}', ("import", '"a.jx" as A')),
        ("{# css 'a.css' #}", ("css", "'a.css'")),
        # No payload: always been a no-op, kept that way.
        ("{# def #}", None),
        ("{# def  #}", None),
        # Not a declaration keyword.
        ("{# note #}", None),
        ("{# defer a #}", None),
        # The keyword has to be separated from the payload.
        ("{#defa#}", None),
    ],
)
def test_split_declaration(comment, expected):
    found = split_declaration(comment)
    assert (found[:2] if found else None) == expected


# --- inline comments inside a declaration -----------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ('"a.css" # a note', '"a.css"'),
        ('"a.css"  #note\n, "b.css"', '"a.css"\n, "b.css"'),
        # A `#` inside quotes is a URL fragment, not a comment.
        ('"/style.css#v2"', '"/style.css#v2"'),
        ('"/style.css#v2" # versioned', '"/style.css#v2"'),
        ("'/a.js#mod'", "'/a.js#mod'"),
        ("no comment here", "no comment here"),
    ],
)
def test_strip_inline_comments(text, expected):
    assert strip_inline_comments(text) == expected


# --- the tree carries them --------------------------------------------------


def test_declarations_land_in_the_ast():
    document = parse_ast(
        '{# def title: str #}\n{# import "card.jx" as Card #}\n<Card />'
    )
    assert [(d.keyword, d.expr) for d in document.declarations] == [
        ("def", "title: str"),
        ("import", '"card.jx" as Card'),
    ]
    assert [d.span.line for d in document.declarations] == [1, 2]


def test_the_comments_are_still_emitted():
    """Declarations are Jinja comments; the generated source keeps them."""
    from proper.jx.parser import JxParser

    source = "{# def title #}\n<div>{{ title }}</div>"
    result, _ = JxParser(name="t", source=source, components=[]).parse()
    assert result.startswith("{# def title #}")
