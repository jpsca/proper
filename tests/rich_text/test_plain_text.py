from proper.rich_text.plain_text import to_plain_text


def test_empty_html():
    assert to_plain_text("") == ""


def test_single_paragraph():
    assert to_plain_text("<p>Hello</p>") == "Hello"


def test_two_paragraphs_separated_by_blank_line():
    assert to_plain_text("<p>A</p><p>B</p>") == "A\n\nB"


def test_heading_is_own_line():
    assert to_plain_text("<h1>Title</h1><p>Body</p>") == "Title\n\nBody"


def test_list_items_with_dashes():
    html = "<ul><li>one</li><li>two</li></ul>"
    assert to_plain_text(html) == "- one\n- two"


def test_quote():
    assert to_plain_text("<blockquote><p>Quoted</p></blockquote>") == "Quoted"


def test_code_block():
    assert to_plain_text("<pre><code>x = 1</code></pre>") == "x = 1"


def test_br_becomes_newline():
    assert to_plain_text("<p>A<br>B</p>") == "A\nB"


def test_hr_renders_dashes():
    assert "---" in to_plain_text("<hr>")


def test_link_text_preserved():
    assert to_plain_text('<p><a href="https://x">click</a></p>') == "click"


def test_inline_marks_stripped():
    assert to_plain_text("<p><strong>bold</strong> <em>it</em></p>") == "bold it"


def test_attachment_with_alt():
    html = '<proper-attachment sgid="abc" alt="Mi gato"></proper-attachment>'
    assert to_plain_text(html) == "[Mi gato]"


def test_attachment_with_filename_fallback():
    class FakeAttachment:
        filename = "photo.jpg"

    html = '<proper-attachment sgid="abc"></proper-attachment>'
    assert to_plain_text(html, attachments={"abc": FakeAttachment()}) == "[photo.jpg]"


def test_attachment_with_empty_filename_falls_through_to_file():
    class FakeAttachment:
        filename = ""

    html = '<proper-attachment sgid="abc"></proper-attachment>'
    assert to_plain_text(html, attachments={"abc": FakeAttachment()}) == "[file]"


def test_attachment_with_caption_when_no_alt_or_filename():
    html = '<proper-attachment sgid="abc" caption="hello"></proper-attachment>'
    assert to_plain_text(html) == "[hello]"


def test_attachment_no_alt_no_attachment_provided():
    html = '<proper-attachment sgid="abc"></proper-attachment>'
    assert to_plain_text(html) == "[file]"


def test_non_string_returns_empty():
    assert to_plain_text(None) == ""  # type: ignore


def test_html_entities_decoded():
    assert to_plain_text("<p>a &amp; b</p>") == "a & b"


def test_script_content_stripped():
    """Script bodies should not leak into plain-text output (search/email)."""
    html = '<p>safe</p><script>alert("bad")</script>'
    out = to_plain_text(html)
    assert "safe" in out
    assert "alert" not in out


def test_image_gallery_passes_attachments_through():
    """A gallery wrapping image attachments emits each child's plain-text
    representation. The gallery wrapper is invisible in plain-text."""
    html = (
        '<div class="rich-text-gallery">'
        '<proper-attachment sgid="a" alt="sunset"></proper-attachment>'
        '<proper-attachment sgid="b" alt="tree"></proper-attachment>'
        '</div>'
    )
    out = to_plain_text(html)
    assert "[sunset]" in out
    assert "[tree]" in out
