from proper.rich_text.plain_text import to_plain_text


def test_empty_doc():
    assert to_plain_text({"type": "doc", "content": []}) == ""


def test_single_paragraph():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
        ],
    }
    assert to_plain_text(ast) == "Hello"


def test_two_paragraphs_separated_by_blank_line():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "A"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "B"}]},
        ],
    }
    assert to_plain_text(ast) == "A\n\nB"


def test_heading_is_own_line():
    ast = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Title"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Body"}]},
        ],
    }
    assert to_plain_text(ast) == "Title\n\nBody"


def test_list_items_with_dashes():
    ast = {
        "type": "doc",
        "content": [
            {"type": "bullet_list", "content": [
                {"type": "list_item", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "one"}]},
                ]},
                {"type": "list_item", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "two"}]},
                ]},
            ]},
        ],
    }
    assert to_plain_text(ast) == "- one\n- two"


def test_blockquote_paragraph_block():
    ast = {
        "type": "doc",
        "content": [
            {"type": "blockquote", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Quoted"}]},
            ]},
        ],
    }
    assert to_plain_text(ast) == "Quoted"


def test_hard_break():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "A"},
                {"type": "hard_break"},
                {"type": "text", "text": "B"},
            ]},
        ],
    }
    assert to_plain_text(ast) == "A\nB"


def test_horizontal_rule_renders_dashes():
    ast = {
        "type": "doc",
        "content": [
            {"type": "horizontal_rule"},
        ],
    }
    assert "---" in to_plain_text(ast)


def test_attachment_with_alt():
    ast = {
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": "abc", "alt": "Mi gato"}},
        ],
    }
    assert to_plain_text(ast) == "[Mi gato]"


def test_attachment_with_filename_fallback():
    class FakeAttachment:
        filename = "photo.jpg"

    ast = {
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": "abc"}},
        ],
    }
    assert to_plain_text(ast, attachments={"abc": FakeAttachment()}) == "[photo.jpg]"


def test_attachment_with_empty_filename_falls_through_to_file():
    class FakeAttachment:
        filename = ""

    ast = {
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": "abc"}},
        ],
    }
    assert to_plain_text(ast, attachments={"abc": FakeAttachment()}) == "[file]"


def test_attachment_no_alt_no_attachment_provided():
    ast = {
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": "abc"}},
        ],
    }
    assert to_plain_text(ast) == "[file]"


def test_non_dict_root_returns_empty():
    assert to_plain_text("not a dict") == ""  # type: ignore


def test_marks_do_not_alter_text():
    ast = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "hello", "marks": [{"type": "bold"}]},
            ]},
        ],
    }
    assert to_plain_text(ast) == "hello"


def test_unknown_node_type_passes_children_through():
    ast = {
        "type": "doc",
        "content": [
            {"type": "unknown_wrapper", "content": [
                {"type": "text", "text": "inner"},
            ]},
        ],
    }
    assert to_plain_text(ast) == "inner"
