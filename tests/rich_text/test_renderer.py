from proper.rich_text.document import replace_attachments


# ── no attachments ──────────────────────────────────────────────────


def test_empty_html_returns_empty():
    assert replace_attachments("") == ""


def test_html_without_attachments_unchanged():
    html = "<p>Hello <strong>world</strong></p>"
    assert replace_attachments(html) == html


def test_html_without_attachments_ignores_renderer():
    def boom(_attrs):
        raise AssertionError("renderer should not be called")

    assert replace_attachments("<p>nothing</p>", boom) == "<p>nothing</p>"


# ── attachment replacement ──────────────────────────────────────────


def test_no_renderer_drops_attachment_tag():
    html = '<p>before</p><proper-attachment sgid="abc"></proper-attachment><p>after</p>'
    assert replace_attachments(html) == "<p>before</p><p>after</p>"


def test_renderer_receives_attrs():
    seen: list[dict[str, str]] = []

    def my_renderer(attrs):
        seen.append(attrs)
        return f"<figure data-id='{attrs['sgid']}'></figure>"

    html = (
        '<p>Look:</p>'
        '<proper-attachment sgid="abc-123" alt="x" filename="cat.png"></proper-attachment>'
    )
    out = replace_attachments(html, my_renderer)
    assert "<p>Look:</p>" in out
    assert "<figure data-id='abc-123'>" in out
    assert seen[0]["sgid"] == "abc-123"
    assert seen[0]["alt"] == "x"
    assert seen[0]["filename"] == "cat.png"


def test_renderer_called_per_attachment():
    seen_ids: list[str] = []

    def my_renderer(attrs):
        seen_ids.append(attrs["sgid"])
        return f"[{attrs['sgid']}]"

    html = (
        '<proper-attachment sgid="a"></proper-attachment>'
        '<proper-attachment sgid="b"></proper-attachment>'
        '<proper-attachment sgid="a"></proper-attachment>'
    )
    out = replace_attachments(html, my_renderer)
    assert out == "[a][b][a]"
    assert seen_ids == ["a", "b", "a"]


def test_renderer_returning_empty_drops_tag():
    """When the renderer returns '' (e.g. attachment row was purged),
    the placeholder is dropped from the output."""
    html = '<p>x</p><proper-attachment sgid="gone"></proper-attachment><p>y</p>'
    assert replace_attachments(html, lambda _a: "") == "<p>x</p><p>y</p>"


def test_renderer_returning_none_drops_tag():
    """Defensive: a renderer that returns None (forgot the return) is
    treated like an empty string rather than blowing up the page."""
    html = '<proper-attachment sgid="x"></proper-attachment>'
    assert replace_attachments(html, lambda _a: None) == ""  # type: ignore


def test_tag_with_inner_content_replaced_whole():
    """Lexxy may store caption HTML inside the tag body. The replacement
    consumes the inner content; the renderer decides what to emit."""
    html = (
        '<proper-attachment sgid="x" caption="hi">'
        '<figcaption>hi</figcaption>'
        '</proper-attachment>'
    )
    out = replace_attachments(html, lambda attrs: f"[{attrs.get('caption', '')}]")
    assert out == "[hi]"


def test_tag_matching_is_case_insensitive():
    html = '<PROPER-ATTACHMENT SGID="x"></PROPER-ATTACHMENT>'
    out = replace_attachments(html, lambda attrs: f"[{attrs.get('sgid', '')}]")
    assert out == "[x]"


# ── defensive ───────────────────────────────────────────────────────


def test_non_string_input_returns_empty():
    assert replace_attachments(None) == ""  # type: ignore
    assert replace_attachments(123) == ""  # type: ignore
