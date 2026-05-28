"""Rich text HTML → plain text extractor.

Used by `RichTextDocument.__str__` for search indices, OG meta tags,
email previews, and any other place that wants the textual content of
a rich document without markup.

Layout rules:
- Block-level tags (`<p>`, `<h*>`, `<blockquote>`, `<pre>`, `<div>`,
  `<figure>`) separate with a blank line (`\\n\\n`).
- `<li>` items get a leading `- ` and end with a newline.
- `<br>` becomes `\\n`; `<hr>` becomes `\\n---\\n`.
- `<proper-attachment>` emits the first that is available between
`alt`, `caption`, or `filename`; else `[file]` as a defensive fallback.
- Unknown tags are stripped but their text content passes through.
"""
import typing as t
from html.parser import HTMLParser


if t.TYPE_CHECKING:
    from ..storage import _Attachment


_BLOCK_TAGS = frozenset({
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "pre", "figure", "figcaption",
    "ul", "ol", "table", "tr",
})
_SKIP_CONTENT = frozenset({"script", "style"})


class _PlainTextExtractor(HTMLParser):
    def __init__(self, attachments: "dict[str, _Attachment]") -> None:
        super().__init__(convert_charrefs=True)
        self._attachments = attachments
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in _SKIP_CONTENT:
            self._skip_depth += 1
            return

        if tag == "proper-attachment":
            self._parts.append(_render_attachment(dict(attrs), self._attachments))
            return

        if tag == "br":
            self._parts.append("\n")
            return

        if tag == "hr":
            self._parts.append("\n---\n")
            return

        if tag == "li":
            self._parts.append("- ")
            return

        if tag in _BLOCK_TAGS:
            self._parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_CONTENT and self._skip_depth > 0:
            self._skip_depth -= 1
            return

        if tag == "li":
            self._parts.append("\n")
            return

        if tag in _BLOCK_TAGS:
            self._parts.append("\n\n")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]],
    ) -> None:
        # `<proper-attachment />` self-closing form, or `<br/>`, `<hr/>`.
        if tag == "proper-attachment":
            self._parts.append(_render_attachment(dict(attrs), self._attachments))
        elif tag == "br":
            self._parts.append("\n")
        elif tag == "hr":
            self._parts.append("\n---\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    def get_text(self) -> str:
        return _collapse_whitespace("".join(self._parts))


def to_plain_text(
    html: str,
    attachments: "dict[str, _Attachment] | None" = None,
) -> str:
    """Render rich text HTML as plain text."""
    if not isinstance(html, str) or not html:
        return ""
    parser = _PlainTextExtractor(attachments or {})
    parser.feed(html)
    parser.close()
    return parser.get_text()


def _render_attachment(
    attrs: dict[str, str | None],
    attachments: "dict[str, _Attachment]",
) -> str:
    alt = attrs.get("alt")
    if alt:
        return f"[{alt}]"

    caption = attrs.get("caption")
    if caption:
        return f"[{caption}]"

    sgid = attrs.get("sgid") or ""
    att = attachments.get(sgid)
    if att is not None and getattr(att, "filename", ""):
        return f"[{att.filename}]"

    return "[file]"


def _collapse_whitespace(text: str) -> str:
    """Trim leading/trailing whitespace and squash runs of 3+ newlines
    down to the two-newline paragraph break."""
    lines = text.split("\n")
    # Strip trailing spaces from each line, then rejoin.
    lines = [ln.rstrip() for ln in lines]
    text = "\n".join(lines)
    # Collapse 3+ consecutive newlines into 2.
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()
