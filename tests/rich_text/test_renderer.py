"""Tests for proper.rich_text.renderer - AST → HTML walker."""
from proper.rich_text.renderer import render


# ── structural nodes ────────────────────────────────────────────────


def test_empty_doc():
    assert render({"type": "doc", "content": []}) == ""


def test_paragraph_with_text():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
        ],
    }
    assert render(ast) == "<p>Hello</p>"


def test_heading_with_level():
    ast = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": "Title"}],
            },
        ],
    }
    assert render(ast) == "<h3>Title</h3>"


def test_heading_default_level_is_1():
    ast = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Title"}]},
        ],
    }
    assert render(ast) == "<h1>Title</h1>"


def test_heading_invalid_level_falls_back_to_1():
    ast = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 99},
                "content": [{"type": "text", "text": "Title"}],
            },
        ],
    }
    assert render(ast) == "<h1>Title</h1>"


def test_blockquote():
    ast = {
        "type": "doc",
        "content": [
            {"type": "blockquote", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Q"}]},
            ]},
        ],
    }
    assert render(ast) == "<blockquote><p>Q</p></blockquote>"


def test_code_block_without_language():
    ast = {
        "type": "doc",
        "content": [
            {"type": "code_block", "content": [{"type": "text", "text": "x = 1"}]},
        ],
    }
    assert render(ast) == "<pre><code>x = 1</code></pre>"


def test_code_block_with_language():
    ast = {
        "type": "doc",
        "content": [
            {
                "type": "code_block",
                "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "x = 1"}],
            },
        ],
    }
    assert render(ast) == '<pre><code class="language-python">x = 1</code></pre>'


def test_bullet_list():
    ast = {
        "type": "doc",
        "content": [
            {"type": "bullet_list", "content": [
                {"type": "list_item", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "a"}]},
                ]},
            ]},
        ],
    }
    assert render(ast) == "<ul><li><p>a</p></li></ul>"


def test_ordered_list():
    ast = {
        "type": "doc",
        "content": [
            {"type": "ordered_list", "content": [
                {"type": "list_item", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "a"}]},
                ]},
            ]},
        ],
    }
    assert render(ast) == "<ol><li><p>a</p></li></ol>"


def test_horizontal_rule():
    ast = {"type": "doc", "content": [{"type": "horizontal_rule"}]}
    assert render(ast) == "<hr>"


def test_hard_break():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "a"},
                {"type": "hard_break"},
                {"type": "text", "text": "b"},
            ]},
        ],
    }
    assert render(ast) == "<p>a<br>b</p>"


# ── text & marks ────────────────────────────────────────────────────


def test_text_is_html_escaped():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "<script>alert(1)</script>"},
            ]},
        ],
    }
    assert render(ast) == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"


def test_bold_mark():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "bold", "marks": [{"type": "bold"}]},
            ]},
        ],
    }
    assert render(ast) == "<p><strong>bold</strong></p>"


def test_italic_mark():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "it", "marks": [{"type": "italic"}]},
            ]},
        ],
    }
    assert render(ast) == "<p><em>it</em></p>"


def test_strike_mark():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "s", "marks": [{"type": "strike"}]},
            ]},
        ],
    }
    assert render(ast) == "<p><s>s</s></p>"


def test_code_mark():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "c", "marks": [{"type": "code"}]},
            ]},
        ],
    }
    assert render(ast) == "<p><code>c</code></p>"


def test_multiple_marks_nest():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [
                    {"type": "bold"}, {"type": "italic"},
                ]},
            ]},
        ],
    }
    # Marks applied in order: bold wraps text first, italic wraps the result.
    assert render(ast) == "<p><em><strong>x</strong></em></p>"


def test_unknown_mark_drops_to_plain_text():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [{"type": "glow"}]},
            ]},
        ],
    }
    assert render(ast) == "<p>x</p>"


# ── link sanitization ───────────────────────────────────────────────


def test_https_link():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "click", "marks": [
                    {"type": "link", "attrs": {"href": "https://example.com"}},
                ]},
            ]},
        ],
    }
    assert render(ast) == '<p><a href="https://example.com">click</a></p>'


def test_http_link():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [
                    {"type": "link", "attrs": {"href": "http://x"}},
                ]},
            ]},
        ],
    }
    assert '<a href="http://x">' in render(ast)


def test_mailto_link():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "mail", "marks": [
                    {"type": "link", "attrs": {"href": "mailto:a@b.com"}},
                ]},
            ]},
        ],
    }
    assert '<a href="mailto:a@b.com">' in render(ast)


def test_tel_link():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "call", "marks": [
                    {"type": "link", "attrs": {"href": "tel:+1234"}},
                ]},
            ]},
        ],
    }
    assert '<a href="tel:+1234">' in render(ast)


def test_javascript_link_dropped():
    """An unsafe scheme strips the link mark but keeps the visible text."""
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "evil", "marks": [
                    {"type": "link", "attrs": {"href": "javascript:alert(1)"}},
                ]},
            ]},
        ],
    }
    rendered = render(ast)
    assert "<a" not in rendered
    assert "evil" in rendered
    assert "javascript" not in rendered


def test_data_url_link_dropped():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [
                    {"type": "link", "attrs": {"href": "data:text/html,<script>"}},
                ]},
            ]},
        ],
    }
    rendered = render(ast)
    assert "<a" not in rendered


def test_link_missing_href_dropped():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [{"type": "link"}]},
            ]},
        ],
    }
    rendered = render(ast)
    assert "<a" not in rendered
    assert "x" in rendered


def test_link_href_html_escaped():
    """A safe URL with quotes/ampersands must still be HTML-escaped in
    the rendered href, so a crafted URL can't break out of the attribute.
    """
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [
                    {"type": "link", "attrs": {"href": 'https://x?a=1&b="2"'}},
                ]},
            ]},
        ],
    }
    rendered = render(ast)
    assert '"' not in rendered.split('href="')[1].split('"')[0].replace("https", "https")
    # easier assertion: the raw " is escaped to &#34; or &quot;
    assert "&quot;" in rendered or "&#34;" in rendered


# ── attachments ─────────────────────────────────────────────────────


def test_attachment_without_renderer_collapses_to_empty():
    ast = {
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": "abc"}},
        ],
    }
    assert render(ast) == ""


def test_attachment_with_renderer_callback():
    seen: list[dict] = []

    def my_renderer(node):
        seen.append(node)
        return f"<figure data-id='{node['attrs']['id']}'></figure>"

    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Look:"}]},
            {"type": "attachment", "attrs": {"id": "abc-123", "alt": "x"}},
        ],
    }
    rendered = render(ast, attachment_renderer=my_renderer)
    assert "<p>Look:</p>" in rendered
    assert "<figure data-id='abc-123'>" in rendered
    assert seen[0]["attrs"]["id"] == "abc-123"


# ── unknown / defensive ─────────────────────────────────────────────


def test_unknown_node_type_renders_empty():
    ast = {
        "type": "doc",
        "content": [
            {"type": "iframe"},
            {"type": "paragraph", "content": [{"type": "text", "text": "ok"}]},
        ],
    }
    assert render(ast) == "<p>ok</p>"


def test_non_dict_root_renders_empty():
    assert render("not a dict") == ""  # type: ignore


def test_link_with_non_string_href_dropped():
    """Defensive: a malformed AST with a non-string href shouldn't crash."""
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "x", "marks": [
                    {"type": "link", "attrs": {"href": 123}},
                ]},
            ]},
        ],
    }
    rendered = render(ast)
    assert "<a" not in rendered
    assert "x" in rendered
