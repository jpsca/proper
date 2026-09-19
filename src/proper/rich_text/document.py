"""`RichTextDocument` - the runtime value of a `RichTextField`.

Holds the HTML string produced by the editor (Lexxy, configured to emit
`<proper-attachment sgid="...">` tags as attachment placeholders) plus
enough wiring to render it. Two display paths:

- `__html__()` returns the HTML with each `<proper-attachment>` tag
  replaced by the `RichTextAttachment` Jx partial. Pre-fetches all
  referenced `Attachment` rows in one query so embeds render without
  N+1.
- `__str__()` returns plain text (paragraph breaks, list bullets,
  bracketed alt text or filenames for embeds). Useful for search
  indices, OG tags, email previews.

When `attachment_cls` is not provided the document still renders, but
`<proper-attachment>` tags collapse to empty markup - the document
doesn't know how to look them up.

**Stored vs. editor HTML.** The editor writes attributes on each tag that
only restate facts about the attachment row (`DERIVED_ATTRS`): its URL,
filename, content type, size and whether it can be previewed. The URL is
signed with the secret keys of the environment that produced it, so a
stored copy stops working when the database moves to another environment
or the keys change. Those attributes are therefore never persisted:

- `dehydrate_attachments()` drops them before the document is stored
  (`RichTextField.db_value`).
- `RichTextDocument.to_editor_html()` rebuilds them from the attachment
  rows when the document is handed to the editor (the form field).

What is stored is just `sgid` plus what the author typed (`alt`,
`caption`, `presentation`, ...), which is valid anywhere.
"""
import re
import typing as t
from collections.abc import Callable

from markupsafe import Markup, escape

from ..global_context import current
from . import plain_text


if t.TYPE_CHECKING:
    from ..storage import _Attachment


# Lexxy emits `<proper-attachment ...></proper-attachment>` as a paired
# tag (custom element with potential caption/inner content). We match
# the full tag, attribute payload, and any inner body in one go so we
# can both extract IDs and replace the tag with rendered output.
_ATTACHMENT_TAG_RE = re.compile(
    r"<proper-attachment\b([^>]*)>(.*?)</proper-attachment>",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r'([a-zA-Z][a-zA-Z0-9_-]*)\s*=\s*"([^"]*)"')

# Attributes of a `<proper-attachment>` tag that only restate facts about the
# attachment row. Never stored; rebuilt for the editor.
DERIVED_ATTRS = ("url", "filename", "content-type", "filesize", "previewable")

_ATTACHMENT_OPEN_TAG_RE = re.compile(r"<proper-attachment\b([^>]*)>", re.IGNORECASE)
# The leading whitespace keeps `url` from matching inside e.g. `data-url`.
_DERIVED_ATTR_RE = re.compile(
    r"\s+(?:" + "|".join(re.escape(name) for name in DERIVED_ATTRS) + r')\s*=\s*"[^"]*"',
    re.IGNORECASE,
)


class RichTextDocument:
    """Value object for a rich text body."""

    def __init__(
        self,
        html: str,
        attachment_cls: "type[_Attachment] | None" = None,
    ) -> None:
        self._html = html or ""
        self._attachment_cls = attachment_cls
        self._resolved: "dict[str, _Attachment] | None" = None

    def to_html(self) -> str:
        """Return the raw stored HTML. Useful for serialization."""
        return self._html

    def to_editor_html(self) -> str:
        """Return the HTML for the editor: every `<proper-attachment>` tag
        gets its `DERIVED_ATTRS` rebuilt from the attachment row, so the
        URLs are valid in the current environment. One query for all the
        referenced attachments, same as rendering.
        """
        return hydrate_attachments(self._html, self._resolve_attachments())

    @property
    def attachments(self) -> "list[_Attachment]":
        """All `Attachment` rows referenced by `<proper-attachment>` tags,
        in document order, with duplicates dropped.
        """
        resolved = self._resolve_attachments()
        # Preserve doc order; the dict was built from ordered IDs.
        return list(resolved.values())

    def __html__(self) -> Markup:
        resolved = self._resolve_attachments()
        html = replace_attachments(self._html, _make_renderer(resolved))
        return Markup(html)

    def __str__(self) -> str:
        resolved = self._resolve_attachments()
        return plain_text.to_plain_text(self._html, attachments=resolved)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RichTextDocument):
            return self._html == other._html
        if isinstance(other, str):
            return self._html == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"RichTextDocument({self._html!r})"

    # --- Attachment resolution ---

    def _resolve_attachments(self) -> "dict[str, _Attachment]":
        if self._resolved is not None:
            return self._resolved

        ids = _collect_attachment_ids(self._html)
        if not ids or self._attachment_cls is None:
            self._resolved = {}
            return self._resolved

        cls = self._attachment_cls
        rows = cls.select().where(cls.id.in_(ids))  # type: ignore
        by_id = {str(row.id): row for row in rows}
        # Preserve order: dict iteration follows insertion order.
        self._resolved = {pk: by_id[pk] for pk in ids if pk in by_id}
        return self._resolved


def _parse_attrs(raw: str) -> dict[str, str]:
    """Extract `name="value"` pairs from a tag's attribute payload."""
    return {name.lower(): value for name, value in _ATTR_RE.findall(raw)}


def _collect_attachment_ids(html: str) -> list[str]:
    """Walk the HTML and return all attachment IDs (from `sgid` attrs on
    `<proper-attachment>` tags), in document order, duplicates removed
    (keeping first occurrence).
    """
    if not isinstance(html, str):
        return []
    seen: dict[str, None] = {}
    for match in _ATTACHMENT_TAG_RE.finditer(html):
        attrs = _parse_attrs(match.group(1))
        att_id = attrs.get("sgid")
        if att_id and att_id not in seen:
            seen[att_id] = None
    return list(seen.keys())


def dehydrate_attachments(html: str) -> str:
    """Return `html` with the `DERIVED_ATTRS` removed from every
    `<proper-attachment>` tag. Everything else is left byte-for-byte as the
    editor wrote it. This is the form in which documents are stored.
    """
    if not isinstance(html, str) or not html:
        return html

    def _sub(match: re.Match[str]) -> str:
        return f"<proper-attachment{_DERIVED_ATTR_RE.sub('', match.group(1))}>"

    return _ATTACHMENT_OPEN_TAG_RE.sub(_sub, html)


def hydrate_attachments(html: str, resolved: "dict[str, _Attachment]") -> str:
    """Return `html` with the `DERIVED_ATTRS` of every `<proper-attachment>`
    tag rebuilt from its row in `resolved` (attachment ID -> row). Stale
    values already present in a tag are replaced. Tags whose attachment is
    not in `resolved` (e.g. it was deleted) are left without them.

    The values mirror what the direct-upload endpoint returns to the editor
    for a fresh upload.
    """
    if not isinstance(html, str) or not html:
        return html

    def _sub(match: re.Match[str]) -> str:
        payload = _DERIVED_ATTR_RE.sub("", match.group(1))
        att = resolved.get(_parse_attrs(payload).get("sgid", ""))
        if att is None:
            return f"<proper-attachment{payload}>"
        derived = {
            "url": att.url,
            "filename": att.filename,
            "content-type": att.content_type,
            "filesize": att.byte_size,
        }
        if att.is_previewable:
            derived["previewable"] = "true"
        extra = "".join(f' {name}="{escape(value)}"' for name, value in derived.items())
        return f"<proper-attachment{payload}{extra}>"

    return _ATTACHMENT_OPEN_TAG_RE.sub(_sub, html)


_AttachmentRenderer = Callable[[dict[str, str]], str]


def _make_renderer(
    resolved: "dict[str, _Attachment]",
    *,
    tmpl: str = "rich_text_attachment.jx",
) -> _AttachmentRenderer:
    """Return a renderer function that renders the given Jx template with
    the attachment attributes + resolved row as context.

    Arguments:
        resolved:
            A dict mapping attachment IDs (from `sgid` attributes) to resolved
            `Attachment` rows. The document doesn't know how to look up attachments
            itself, so the caller must provide them.
        tmpl:
            The Jx template to render for each attachment. The template receives the
            tag attributes plus an `attachment` kwarg with the resolved row.
    """
    def render_one(attrs: dict[str, str]) -> str:
        att = resolved.get(attrs.get("sgid", ""))
        if att is None:
            return ""
        assert current.app is not None
        kwargs: dict[str, t.Any] = {**attrs, "attachment": att}
        return str(current.app.catalog.render(tmpl, **kwargs))

    return render_one


def replace_attachments(
    html: str,
    renderer: _AttachmentRenderer | None = None,
) -> str:
    """Return `html` with each `<proper-attachment>` tag substituted by
    the output of `renderer(attrs)`.

    Arguments:
        html:
            The rich text HTML to render.
        renderer:
            An renderer function.
    """
    if not isinstance(html, str) or not html:
        return ""
    if renderer is None:
        return _ATTACHMENT_TAG_RE.sub("", html)

    def _sub(match: re.Match[str]) -> str:
        attrs = {name.lower(): value for name, value in _ATTR_RE.findall(match.group(1))}
        return renderer(attrs) or ""

    return _ATTACHMENT_TAG_RE.sub(_sub, html)
