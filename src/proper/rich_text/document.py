"""`RichTextDocument` - the runtime value of a `RichTextField`.

Holds the AST (a plain dict) plus enough wiring to render it.
Two display paths:

- `__html__()` builds an HTML string. Pre-fetches all referenced
  `Attachment` rows in one query and routes each embed through the
  `RichTextAttachment` Jx component (so users own the visual layout
  of embeds via that component, not via framework code).
- `__str__()` returns plain text (paragraph breaks, list bullets,
  bracketed alt text or filenames for embeds). Useful for search
  indices, OG tags, email previews.

When `attachment_cls` is not provided the document still renders, but
`attachment` nodes collapse to empty markup - the document doesn't
know how to look them up.
"""
import typing as t

from markupsafe import Markup

from ..global_context import current
from . import plain_text, renderer


if t.TYPE_CHECKING:
    from ..types import TAttachment


class RichTextDocument:
    """Value object for a rich text body."""

    def __init__(
        self,
        data: dict,
        attachment_cls: "type[TAttachment] | None" = None,
    ) -> None:
        self._data = data
        self._attachment_cls = attachment_cls
        self._resolved: "dict[str, TAttachment] | None" = None

    def to_dict(self) -> dict:
        """Return the raw AST as a plain dict. Useful for serialization."""
        return self._data

    @property
    def attachments(self) -> "list[TAttachment]":
        """All `Attachment` rows referenced by `attachment` nodes,
        in document order, with duplicates dropped.
        """
        resolved = self._resolve_attachments()
        # Preserve doc order; the dict was built from ordered IDs.
        return list(resolved.values())

    def __html__(self) -> Markup:
        resolved = self._resolve_attachments()
        html = renderer.render(
            self._data,
            attachment_renderer=self._make_attachment_renderer(resolved),
        )
        return Markup(html)

    def __str__(self) -> str:
        resolved = self._resolve_attachments()
        return plain_text.to_plain_text(self._data, attachments=resolved)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RichTextDocument):
            return self._data == other._data
        if isinstance(other, dict):
            return self._data == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"RichTextDocument({self._data!r})"

    # ── attachment resolution ────────────────────────────────────────

    def _resolve_attachments(self) -> "dict[str, TAttachment]":
        if self._resolved is not None:
            return self._resolved

        ids = _collect_attachment_ids(self._data)
        if not ids or self._attachment_cls is None:
            self._resolved = {}
            return self._resolved

        cls = self._attachment_cls
        rows = cls.select().where(cls.id.in_(ids)) # type: ignore
        by_id = {str(row.id): row for row in rows}
        # Preserve order: dict iteration follows insertion order.
        self._resolved = {pk: by_id[pk] for pk in ids if pk in by_id}
        return self._resolved

    def _make_attachment_renderer(
        self,
        resolved: "dict[str, TAttachment]",
    ) -> renderer.AttachmentRenderer:
        def render_one(node: dict) -> str:
            attrs = node.get("attrs") or {}
            att = resolved.get(attrs.get("id", ""))
            if att is None:
                return ""
            assert current.app is not None
            return str(current.app.catalog.render(
                "RichTextAttachment",
                attachment=att,
                alt=attrs.get("alt"),
                caption=attrs.get("caption"),
            ))

        return render_one


def _collect_attachment_ids(node: t.Any) -> list[str]:
    """Walk the AST and return all attachment IDs, in document order,
    duplicates removed (keeping first occurrence).
    """
    seen: dict[str, None] = {}
    _collect(node, seen)
    return list(seen.keys())


def _collect(node: t.Any, seen: "dict[str, None]") -> None:
    if not isinstance(node, dict):
        return
    if node.get("type") == "attachment":
        att_id = (node.get("attrs") or {}).get("id")
        if isinstance(att_id, str) and att_id not in seen:
            seen[att_id] = None
    for child in node.get("content") or ():
        _collect(child, seen)
