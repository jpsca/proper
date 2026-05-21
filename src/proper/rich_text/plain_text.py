"""AST → plain text walker.

Used by `RichTextDocument.__str__` for search indices, OG meta tags,
email previews, and any other place that wants the textual content of
a rich document without markup.

Layout rules:
- Paragraphs and other blocks separate with a blank line (`\\n\\n`).
- Headings are on their own line.
- List items get a leading `- `.
- Attachments emit `[alt]` if alt text is set, else `[filename]` if
  the attachment was provided, else `[file]` as a defensive fallback.
- Hard breaks become `\\n`; horizontal rules become `\\n---\\n`.
- Unknown node types are skipped silently (their children, if any, still
  render - useful so future node types added by editors don't blow up
  past plain-text extraction).
"""
import typing as t


if t.TYPE_CHECKING:
    from ..types import TAttachment


def to_plain_text(
    ast: dict,
    attachments: "dict[str, TAttachment] | None" = None,
) -> str:
    """Render a rich text AST as plain text."""
    return _walk(ast, attachments or {}).strip()


def _walk(node: t.Any, attachments: "dict[str, TAttachment]") -> str:
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")

    if node_type == "text":
        return str(node.get("text", ""))

    if node_type == "attachment":
        return _render_attachment(node, attachments)

    if node_type == "hard_break":
        return "\n"

    if node_type == "horizontal_rule":
        return "\n---\n"

    children_text = "".join(_walk(c, attachments) for c in node.get("content") or ())

    if node_type == "list_item":
        return f"- {children_text.strip()}\n"

    if node_type in ("paragraph", "heading", "blockquote", "code_block"):
        return children_text + "\n\n"

    # doc, bullet_list, ordered_list, unknown - pass children through
    return children_text


def _render_attachment(
    node: dict,
    attachments: "dict[str, TAttachment]",
) -> str:
    attrs = node.get("attrs") or {}
    alt = attrs.get("alt")
    if alt:
        return f"[{alt}]"

    att = attachments.get(attrs.get("id", ""))
    if att is not None and getattr(att, "filename", ""):
        return f"[{att.filename}]"

    return "[file]"
