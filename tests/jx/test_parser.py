"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import jinja2
import pytest

from proper.jx import TemplateSyntaxError
from proper.jx.parser import JxParser


VALID_DATA = (
    # Simple case
    (
        """<Foo bar="baz">content</Foo>""",
        """{% call _render("Foo", **{"bar":"baz"}) -%}content{%- endcall %}""",
    ),
    # Self-closing tag
    (
        """<Alert type="success" message="Success!" />""",
        """{{ _render("Alert", **{"type":"success", "message":"Success!"})|_jx_safe }}""",
    ),
    # No attributes
    (
        """<Foo>content</Foo>""",
        """{% call _render("Foo") -%}content{%- endcall %}""",
    ),
    # No attributes, self-closing tag
    (
        """<Foo />""",
        """{{ _render("Foo")|_jx_safe }}""",
    ),
    # Strings vs expressions
    (
        """<Foo bar="baz" lorem={{ ipsum }}>content</Foo>""",
        """{% call _render("Foo", **{"bar":"baz", "lorem":ipsum}) -%}content{%- endcall %}""",
    ),
    # Single quotes
    (
        """<Foo bar='say "hello world"'>content</Foo>""",
        """{% call _render("Foo", **{"bar":'say "hello world"'}) -%}content{%- endcall %}""",
    ),
    (
        """<Foo bar="say 'hello world'">content</Foo>""",
        """{% call _render("Foo", **{"bar":"say 'hello world'"}) -%}content{%- endcall %}""",
    ),
    # Braces inside quotes
    (
        """<Foo bar="say 'hello {{world}}'">content</Foo>""",
        """{% call _render("Foo", **{"bar":"say 'hello {{world}}'"}) -%}content{%- endcall %}""",
    ),
    # Line breaks
    (
        """<Foo
          bar="baz"
          lorem="ipsum"
        >content</Foo>""",
        """{% call _render("Foo", **{"bar":"baz", "lorem":"ipsum"}) -%}content{%- endcall %}""",
    ),
    # Line breaks, self-closing tag
    (
        """<Foo
          bar="baz"
          lorem="ipsum"
          green
        />""",
        """{{ _render("Foo", **{"bar":"baz", "lorem":"ipsum", "green":True})|_jx_safe }}""",
    ),
    # Python expression in attribute and boolean attributes
    (
        """<Foo bar={{ 42 + 4 }} green large>content</Foo>""",
        """{% call _render("Foo", **{"bar":42 + 4, "green":True, "large":True}) -%}content{%- endcall %}""",
    ),
    # `>` in expression
    (
        """<CloseBtn disabled={{ num > 4 }} />""",
        """{{ _render("CloseBtn", **{"disabled":num > 4})|_jx_safe }}""",
    ),
    # `>` in attribute value
    (
        """<CloseBtn data-closer-action="click->closer#close" />""",
        """{{ _render("CloseBtn", **{"data_closer_action":"click->closer#close"})|_jx_safe }}""",
    ),
    # Quotes inside expressions (should not break parsing)
    (
        """<Card title={{ items['key'] }} class="foo" />""",
        """{{ _render("Card", **{"title":items['key'], "class":"foo"})|_jx_safe }}""",
    ),
    (
        """<Card title={{ data["name"] }} />""",
        """{{ _render("Card", **{"title":data["name"]})|_jx_safe }}""",
    ),
    # Closing braces inside string literals within expressions
    (
        """<Card title={{ foo("}}") }} />""",
        """{{ _render("Card", **{"title":foo("}}")})|_jx_safe }}""",
    ),
    (
        """<Card title={{ foo('}}') }} />""",
        """{{ _render("Card", **{"title":foo('}}')})|_jx_safe }}""",
    ),
    (
        """<Card title={{ "it's }}" }} />""",
        """{{ _render("Card", **{"title":"it's }}"})|_jx_safe }}""",
    ),
    # Raw blocks
    (
        """<Foo bar="baz">content</Foo>
{% raw %}{{ a + b }}{% endraw %}
what""",
        """{% call _render("Foo", **{"bar":"baz"}) -%}content{%- endcall %}
{% raw %}{{ a + b }}{% endraw %}
what""",
    ),
    # A `{%` inside a raw block is text, not the start of a statement.
    (
        """{% raw %}Use {% in a sentence{% endraw %}<Foo />""",
        """{% raw %}Use {% in a sentence{% endraw %}{{ _render("Foo")|_jx_safe }}""",
    ),
    # Raw blocks with HTML content (should not be escaped)
    (
        """<Foo bar="baz">content</Foo>
{% raw %}<div class="test">&amp;</div>{% endraw %}""",
        """{% call _render("Foo", **{"bar":"baz"}) -%}content{%- endcall %}
{% raw %}<div class="test">&amp;</div>{% endraw %}""",
    ),
)


@pytest.mark.parametrize("source, expected", VALID_DATA)
def test_process_valid_tags(source, expected):
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    print(result)
    assert result == expected


INVALID_DATA = (
    # Tag not closed
    (
        """<Foo bar="baz">content aslasals ls,als,as""",
        TemplateSyntaxError,
        "Unclosed component",
    ),
    # String attribute not closed
    (
        """<Foo bar="baz>content lorem ipsumsdsd""",
        TemplateSyntaxError,
        "Syntax error",
    ),
    # Expression not closed
    (
        """<Foo bar={{ 42 + 4>content</Foo>""",
        TemplateSyntaxError,
        "Syntax error",
    ),
    # Unmatched braces
    (
        """<Foo bar={{ 42 + {{ 4 }}>content</Foo>""",
        TemplateSyntaxError,
        "Unmatched braces",
    ),
    (
        """<Foo bar=42 + 4}}>content</Foo>""",
        TemplateSyntaxError,
        "Unmatched braces",
    ),
)


@pytest.mark.parametrize("source, exception, match", INVALID_DATA)
def test_process_invalid_tags(source, exception, match):
    parser = JxParser(name="test", source=source, components=[])
    with pytest.raises(exception, match=f".*{match}.*"):
        parser.parse(validate_tags=False)


def test_process_nested_same_tag():
    source = """
<Card class="card">
  WTF
  <Card class="card-header">abc</Card>
  <Card class="card-body">
    <div><Card>Text</Card></div>
  </Card>
</Card>
    """
    expected = """
{% call _render("Card", **{"class":"card"}) -%}
  WTF
  {% call _render("Card", **{"class":"card-header"}) -%}abc{%- endcall %}
  {% call _render("Card", **{"class":"card-body"}) -%}
    <div>{% call _render("Card") -%}Text{%- endcall %}</div>
  {%- endcall %}
{%- endcall %}
"""
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    print(result)
    assert result.strip() == expected.strip()


def test_nested_same_tag_with_content_between():
    """Content between nested same-name closing tags is preserved."""
    source = """<Card>a<Card>b</Card>c</Card>"""
    expected = (
        '{% call _render("Card") -%}'
        'a{% call _render("Card") -%}b{%- endcall %}c'
        '{%- endcall %}'
    )
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    assert result == expected


def test_nested_same_tag_self_closing_does_not_increase_depth():
    """Self-closing same-name tags inside a block don't affect nesting."""
    source = """<Card>a<Card />b</Card>"""
    expected = (
        '{% call _render("Card") -%}'
        'a{{ _render("Card")|_jx_safe }}b'
        '{%- endcall %}'
    )
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    assert result == expected


def test_nested_same_tag_siblings():
    """Multiple same-name siblings inside a parent of the same name."""
    source = """<Card><Card>a</Card><Card>b</Card></Card>"""
    expected = (
        '{% call _render("Card") -%}'
        '{% call _render("Card") -%}a{%- endcall %}'
        '{% call _render("Card") -%}b{%- endcall %}'
        '{%- endcall %}'
    )
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    assert result == expected


def test_nested_same_tag_unclosed():
    """An unclosed nested same-name tag is reported."""
    source = """<Card><Card>a</Card>"""
    parser = JxParser(name="test", source=source, components=[])
    with pytest.raises(TemplateSyntaxError, match="Unclosed component"):
        parser.parse(validate_tags=False)


def test_validate_tags():
    source = """<Button><Icon name="alert" /> Click me</Button>"""
    parser = JxParser(name="test", source=source, components=["Button"])
    with pytest.raises(TemplateSyntaxError, match="Unknown component `Icon`.*"):
        parser.parse(validate_tags=True)


def test_error_lineno_after_multiline_tag():
    """Error line numbers stay correct after a multi-line tag replacement."""
    source = (
        '<Valid\n'
        '  foo="bar"\n'
        '  baz="qux"\n'
        '/>\n'
        '<Unknown />\n'
    )
    parser = JxParser(name="test", source=source, components=["Valid"])
    with pytest.raises(TemplateSyntaxError, match=r"\[test:5:0\] Unknown component `Unknown`"):
        parser.parse(validate_tags=True)


def test_slots():
    source = """
<html>
  {% slot header %}
  <h1>Header</h1>
  {% endslot %}

  <p>Main content</p>
  {% if user %}
    <p>Hi, {{ user }}!</p>
  {% endif %}

  {% slot footer %}
    <footer>Footer content</footer>
  {% endslot %}
</html>
    """
    parser = JxParser(name="test", source=source, components=[])
    result, slots = parser.parse(validate_tags=False)
    print(result)

    assert slots == ("header", "footer")
    assert result.strip() == """
<html>
  {% if 'header' in _slots %}{{ _slots['header']()|_jx_safe }}{% else %}
  <h1>Header</h1>
  {% endif %}

  <p>Main content</p>
  {% if user %}
    <p>Hi, {{ user }}!</p>
  {% endif %}

  {% if 'footer' in _slots %}{{ _slots['footer']()|_jx_safe }}{% else %}
    <footer>Footer content</footer>
  {% endif %}
</html>
""".strip()



def test_slots_strip():
    source = """
<html>
  {% slot header %}
  <h1>Header</h1>
  {% endslot %}

  <p>Main content</p>
  {% if user %}
    <p>Hi, {{ user }}!</p>
  {% endif %}

  {% slot footer -%}
    <footer>Footer content</footer>
  {%- endslot %}
</html>
    """
    parser = JxParser(name="test", source=source, components=[])
    result, _ = parser.parse(validate_tags=False)
    print(result)

    assert result.strip() == """
<html>
  {% if 'header' in _slots %}{{ _slots['header']()|_jx_safe }}{% else %}
  <h1>Header</h1>
  {% endif %}

  <p>Main content</p>
  {% if user %}
    <p>Hi, {{ user }}!</p>
  {% endif %}

  {% if 'footer' in _slots %}{{ _slots['footer']()|_jx_safe }}{% else %}<footer>Footer content</footer>{% endif %}
</html>
""".strip()


def test_fills():
    source = """
<Layout>
{% fill header %}
<h1>Header</h1>
{% endfill %}

<p>Main content</p>
<p>Hi, {{ user }}!</p>

{% fill footer %}
<footer>Footer content</footer>
{% endfill %}
</Layout>
    """
    parser = JxParser(name="test", source=source, components=["Layout"])
    result, _ = parser.parse(validate_tags=False)
    print(result)

    assert result.strip() == """
{% macro _jx_fill_1() %}
<h1>Header</h1>
{% endmacro %}{% macro _jx_fill_2() %}
<footer>Footer content</footer>
{% endmacro %}{% call _render("Layout", _fills={"header": _jx_fill_1, "footer": _jx_fill_2}) -%}<p>Main content</p>
<p>Hi, {{ user }}!</p>{%- endcall %}
""".strip()


def test_fills_strip():
    source = """
<Layout>
{% fill header -%}
<h1>Header</h1>
{%- endfill %}

<p>Main content</p>
<p>Hi, {{ user }}!</p>

{% fill footer %}
<footer>Footer content</footer>
{%- endfill %}
</Layout>
    """
    parser = JxParser(name="test", source=source, components=["Layout"])
    result, _ = parser.parse(validate_tags=False)
    print(result)

    assert result.strip() == """
{% macro _jx_fill_1() %}<h1>Header</h1>{% endmacro %}{% macro _jx_fill_2() %}
<footer>Footer content</footer>{% endmacro %}{% call _render("Layout", _fills={"header": _jx_fill_1, "footer": _jx_fill_2}) -%}<p>Main content</p>
<p>Hi, {{ user }}!</p>{%- endcall %}
""".strip()


def test_comment_blocks_are_protected():
    """Component tags inside Jinja comments should not be processed."""
    source = """{# TODO: Use <Card /> here #}\n<Foo>bar</Foo>"""
    parser = JxParser(name="test", source=source, components=["Foo"])
    result, _ = parser.parse(validate_tags=True)
    assert "{# TODO: Use <Card /> here #}" in result
    assert '_render("Foo")' in result


def test_multiline_comment_blocks_are_protected():
    """Multiline Jinja comments with component tags should not be processed."""
    source = """{#\n  <Card title="hello" />\n  <Button />\n#}\n<Foo />"""
    parser = JxParser(name="test", source=source, components=["Foo"])
    result, _ = parser.parse(validate_tags=True)
    assert "<Card" in result
    assert "<Button" in result
    assert '_render("Foo")' in result


def test_malformed_nested_opening_tag():
    """A nested opening tag that can't be parsed is reported at its own position.

    The outer <Foo> is well-formed, but inside it there's another <Foo
    whose opening tag never closes (unmatched braces prevent finding '>').
    Nested tags are processed first, so the error points at the inner tag.
    """
    source = "<Foo>inner <Foo {{ broken</Foo></Foo>"
    parser = JxParser(name="test", source=source, components=["Foo"])
    with pytest.raises(TemplateSyntaxError, match=r"\[test:1:11\] Syntax error: `Foo`"):
        parser.parse()


def test_expr_with_nested_quotes_in_attrs():
    """Expression blocks with quotes inside are handled by _replace_expr_blocks."""
    source = """<Foo bar={{ "hello" + 'world' }}>content</Foo>"""
    parser = JxParser(name="test", source=source, components=["Foo"])
    result, _ = parser.parse()
    assert "_render" in result


def test_unclosed_expr_block_raises():
    """An unclosed {{ is reported, with the position of the opening braces."""
    parser = JxParser(name="test", source="bar={{ oops", components=[])
    with pytest.raises(
        TemplateSyntaxError, match=r"\[test:1:4\] Unclosed expression"
    ):
        parser.parse()


def test_escaped_quotes_in_tag_attrs():
    r"""
    An escaped quote does not end an attribute value.

    The regex parser cut the value at the first `"`, escaped or not, and emitted
    an unterminated Python string literal. Nothing caught it because the
    generated source was never checked, only searched for `_render`.
    """
    source = r"""<Foo title="say \"hello\"" />"""
    parser = JxParser(name="test", source=source, components=["Foo"])
    result, _ = parser.parse()
    assert result == r"""{{ _render("Foo", **{"title":"say \"hello\""})|_jx_safe }}"""
    assert r"\"hello\"" in result


@pytest.mark.parametrize(
    "source, default",
    [
        ("{% slot a %}  d  {% endslot %}", "  d  "),
        ("{% slot a -%}  d  {%- endslot %}", "d"),
        # `+` is the explicit "keep it" marker, so it must not strip.
        ("{% slot a +%}  d  {%+ endslot %}", "  d  "),
        ("{% slot a -%}  d  {%+ endslot %}", "d  "),
        ("{% slot a +%}  d  {%- endslot %}", "  d"),
    ],
)
def test_slot_strips_only_on_the_dash_marker(source, default):
    result, _ = JxParser(name="test", source=source, components=[]).parse()
    assert result == (
        "{% if 'a' in _slots %}{{ _slots['a']()|_jx_safe }}" f"{{% else %}}{default}{{% endif %}}"
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        ("A  {% slot h %}d{% endslot %}  B", "A  d  B"),
        # The generated `{% if %}` replaces the `{% slot %}` tag, so a marker
        # on the tag has to be carried over or Jinja never sees it.
        ("A  {%- slot h %}d{% endslot %}  B", "Ad  B"),
        ("A  {% slot h %}d{% endslot -%}  B", "A  dB"),
        ("A  {%- slot h %}d{% endslot -%}  B", "AdB"),
        # `+` is the explicit "keep it" marker.
        ("A  {%+ slot h %}d{% endslot +%}  B", "A  d  B"),
    ],
)
def test_slot_outer_whitespace_markers(source, expected):
    result, _ = JxParser(name="test", source=source, components=[]).parse()
    env = jinja2.Environment()
    env.globals["_slots"] = {}
    assert env.from_string(result).render() == expected
