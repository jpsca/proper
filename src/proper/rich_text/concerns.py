"""Lifecycle mixin for models that hold rich text bodies.

Mix `HasRichText` into any peewee model that declares one or more
`RichTextField` columns. The mixin overrides `save()` and
`delete_instance()` to keep referenced attachments in sync with the
document:

- **On save**: every attachment that was in the prior body but no longer
  appears in the new body is scheduled for purge; every attachment that
  *does* appear is marked `pending=False` (a single batched UPDATE),
  confirming that some record now owns it.
- **On delete**: every attachment referenced by any rich text column is
  scheduled for purge after the parent row is gone.

The mixin auto-discovers `RichTextField` columns by walking
`cls._meta.fields` and looking for fields with an `attachment_cls`
attribute. No declarative list on the model — the field declaration is
already the source of truth.

Usage::

    from proper.rich_text import HasRichText, RichTextField

    class Post(HasRichText, BaseModel):
        body = RichTextField(attachment_cls=Attachment)
"""
import typing as t


if t.TYPE_CHECKING:
    import peewee as pw


def _iter_rich_text_fields(cls: type) -> "t.Iterator[tuple[str, pw.Field]]":
    """Yield `(field_name, field)` for every RichTextField column.

    Detected by duck-typing on the `attachment_cls` attribute, which
    every field built by `make_rich_text_field` carries. Using a
    structural check rather than `isinstance` lets users build
    alternative parents (Postgres native JSON, etc.) via the factory
    without losing lifecycle support.
    """
    for name, field in cls._meta.fields.items():
        if hasattr(field, "attachment_cls"):
            yield name, field


def _ast_of(value: t.Any) -> t.Any:
    """Coerce a field value (dict, `RichTextDocument`, or `None`) to
    a plain AST dict. `None` and other shapes pass through unchanged.
    """
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _collect_attachment_ids(ast: t.Any) -> list[str]:
    """Walk an AST and return attachment IDs in document order, deduped."""
    if not isinstance(ast, dict):
        return []
    seen: dict[str, None] = {}
    _walk(ast, seen)
    return list(seen.keys())


def _walk(node: t.Any, seen: "dict[str, None]") -> None:
    if not isinstance(node, dict):
        return
    if node.get("type") == "attachment":
        att_id = (node.get("attrs") or {}).get("id")
        if isinstance(att_id, str) and att_id not in seen:
            seen[att_id] = None
    for child in node.get("content") or ():
        _walk(child, seen)


class HasRichText:
    """Mixin that handles RichTextField attachment lifecycle."""

    def save(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        # Snapshot prior body before super().save() overwrites it.
        old_ids_by_field = self._snapshot_rich_text_ids()
        result = super().save(*args, **kwargs)  # type: ignore[misc]
        self._reconcile_rich_text_attachments(old_ids_by_field)
        return result

    def delete_instance(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        # Collect IDs before the parent row vanishes.
        ids_by_field = self._collect_rich_text_ids_now()
        result = super().delete_instance(*args, **kwargs)  # type: ignore[misc]
        self._purge_collected(ids_by_field)
        return result

    # ── helpers ──────────────────────────────────────────────────────

    def _snapshot_rich_text_ids(self) -> "dict[str, list[str]]":
        """Return `{field_name: [old_attachment_ids…]}` for every
        RichTextField column. New (unsaved) records return empty lists —
        there's no prior body to diff against.
        """
        cls = type(self)
        out: dict[str, list[str]] = {}

        # `get_id()` returns the PK value, or None if unsaved.
        pk = self.get_id()  # type: ignore[attr-defined]
        if pk is None:
            for name, _field in _iter_rich_text_fields(cls):
                out[name] = []
            return out

        for name, _field in _iter_rich_text_fields(cls):
            column = getattr(cls, name)
            row = (
                cls.select(column)
                .where(cls._meta.primary_key == pk)
                .first()
            )
            if row is None:
                out[name] = []
            else:
                out[name] = _collect_attachment_ids(_ast_of(getattr(row, name)))
        return out

    def _reconcile_rich_text_attachments(
        self,
        old_ids_by_field: "dict[str, list[str]]",
    ) -> None:
        """Purge attachments that disappeared from each body, mark survivors
        as no-longer-pending.
        """
        cls = type(self)
        for name, field in _iter_rich_text_fields(cls):
            attachment_cls = field.attachment_cls  # type: ignore[attr-defined]
            if attachment_cls is None:
                continue

            new_ids = set(_collect_attachment_ids(_ast_of(getattr(self, name))))
            old_ids = set(old_ids_by_field.get(name, ()))

            for att_id in old_ids - new_ids:
                inst = attachment_cls.get_or_none(attachment_cls.id == att_id)
                if inst is not None:
                    inst.purge_later()

            if new_ids:
                attachment_cls.update(pending=False).where(
                    (attachment_cls.id.in_(new_ids))
                    & (attachment_cls.pending == True)  # noqa: E712
                ).execute()

    def _collect_rich_text_ids_now(self) -> "dict[str, tuple[t.Any, list[str]]]":
        """Snapshot the *current* body of every RichTextField column,
        bundled with the field instance so the caller can find the
        right `attachment_cls` later.
        """
        cls = type(self)
        out: dict[str, tuple[t.Any, list[str]]] = {}
        for name, field in _iter_rich_text_fields(cls):
            out[name] = (field, _collect_attachment_ids(_ast_of(getattr(self, name))))
        return out

    def _purge_collected(
        self,
        ids_by_field: "dict[str, tuple[t.Any, list[str]]]",
    ) -> None:
        for _name, (field, ids) in ids_by_field.items():
            attachment_cls = field.attachment_cls
            if attachment_cls is None:
                continue
            for att_id in ids:
                inst = attachment_cls.get_or_none(attachment_cls.id == att_id)
                if inst is not None:
                    inst.purge_later()
