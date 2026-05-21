"""AST → HTML walker.

The walker only knows about *structural* nodes - paragraphs, headings,
lists, marks, and so on. For `attachment` nodes it delegates to an
`attachment_renderer` callable, which is expected to look up the
referenced `Attachment` and return ready-to-emit HTML (typically by
rendering a Jx component). Keeping that boundary explicit lets the
framework own structural HTML while the user owns the visual
presentation of embeds.

Text content is HTML-escaped. Link `href` attributes are sanitized
against an allowlist of safe URL schemes; an unsafe scheme drops the
link mark (the inner text still renders, without the `<a>` wrapper).
"""
import typing as t
from collections.abc import Callable

from markupsafe import escape


AttachmentRenderer = Callable[[dict], str]


SAFE_LINK_SCHEMES = ("http://", "https://", "mailto:", "tel:")


def render(
    ast: dict,
    *,
    attachment_renderer: AttachmentRenderer | None = None,
) -> str:
    """Render an AST to an HTML string.

    `attachment_renderer` is called with each attachment node and must
    return the HTML for that embed. If `None`, attachment nodes render
    as empty strings.
    """
    return _render_node(ast, attachment_renderer)


def _render_node(
    node: t.Any,
    attachment_renderer: AttachmentRenderer | None,
) -> str:
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type", "")
    handler = _BLOCK_HANDLERS.get(node_type)
    if handler is not None:
        return handler(node, attachment_renderer)

    if node_type == "text":
        return _render_text(node)

    if node_type == "attachment":
        if attachment_renderer is None:
            return ""
        return attachment_renderer(node)

    # Unknown node type: render nothing. Children are not walked, on the
    # principle that we don't know what the unknown wrapper means
    # semantically - emitting orphaned children could produce nonsense.
    return ""


# ── block / structural nodes ────────────────────────────────────────


def _render_doc(node, attachment_renderer):
    return _render_children(node, attachment_renderer)


def _render_paragraph(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    return f"<p>{inner}</p>"


def _render_heading(node, attachment_renderer):
    attrs = node.get("attrs") or {}
    level = attrs.get("level", 1)
    if not isinstance(level, int) or level < 1 or level > 6:
        level = 1
    inner = _render_children(node, attachment_renderer)
    return f"<h{level}>{inner}</h{level}>"


def _render_blockquote(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    return f"<blockquote>{inner}</blockquote>"


def _render_code_block(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    attrs = node.get("attrs") or {}
    lang = attrs.get("language")
    if lang:
        return f'<pre><code class="language-{escape(lang)}">{inner}</code></pre>'
    return f"<pre><code>{inner}</code></pre>"


def _render_bullet_list(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    return f"<ul>{inner}</ul>"


def _render_ordered_list(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    return f"<ol>{inner}</ol>"


def _render_list_item(node, attachment_renderer):
    inner = _render_children(node, attachment_renderer)
    return f"<li>{inner}</li>"


def _render_horizontal_rule(node, attachment_renderer):
    return "<hr>"


def _render_hard_break(node, attachment_renderer):
    return "<br>"


_BLOCK_HANDLERS: dict[str, Callable[[dict, AttachmentRenderer | None], str]] = {
    "doc": _render_doc,
    "paragraph": _render_paragraph,
    "heading": _render_heading,
    "blockquote": _render_blockquote,
    "code_block": _render_code_block,
    "bullet_list": _render_bullet_list,
    "ordered_list": _render_ordered_list,
    "list_item": _render_list_item,
    "horizontal_rule": _render_horizontal_rule,
    "hard_break": _render_hard_break,
}


def _render_children(
    node: dict,
    attachment_renderer: AttachmentRenderer | None,
) -> str:
    return "".join(
        _render_node(child, attachment_renderer)
        for child in node.get("content") or ()
    )


# ── text + marks ────────────────────────────────────────────────────


def _render_text(node: dict) -> str:
    text = escape(node.get("text", ""))
    for mark in node.get("marks") or ():
        text = _apply_mark(mark, text)
    return str(text)


def _apply_mark(mark: dict, text: str) -> str:
    mark_type = mark.get("type")

    if mark_type == "bold":
        return f"<strong>{text}</strong>"
    if mark_type == "italic":
        return f"<em>{text}</em>"
    if mark_type == "strike":
        return f"<s>{text}</s>"
    if mark_type == "code":
        return f"<code>{text}</code>"
    if mark_type == "link":
        href = (mark.get("attrs") or {}).get("href", "")
        if not _is_safe_href(href):
            return text
        return f'<a href="{escape(href)}">{text}</a>'

    # Unknown mark: drop it, keep the text content.
    return text


def _is_safe_href(href: t.Any) -> bool:
    if not isinstance(href, str):
        return False
    lowered = href.lower()
    return any(lowered.startswith(scheme) for scheme in SAFE_LINK_SCHEMES)
