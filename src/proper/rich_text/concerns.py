"""Lifecycle mixin for models that hold rich text bodies.

Mix `HasRichText` into any peewee model that declares one or more
`RichTextField` columns. The mixin overrides `save()` and
`delete_instance()` to keep the attachment references in sync with the
documents.

Each attachment that a rich text body embeds has a row in
`Attachment.Reference` (built by `attachment_for()`, in the storage
addon) that records the table, primary key and column that embed it.
Two records can embed the same attachment: it is purged only when its
last reference goes away.

- **On save**: the references of each rich text column are compared
  with the attachments in its new body. The ones that are no longer
  embedded are removed, the new ones are added, and every attachment
  that lost its last reference is scheduled for purge.
- **On delete**: every reference of the record is removed, and every
  attachment that lost its last reference is scheduled for purge.

The mixin auto-discovers `RichTextField` columns by walking
`cls._meta.fields` and looking for fields with an `attachment_cls`
attribute. No declarative list on the model - the field declaration is
already the source of truth.

Usage::

    from proper.rich_text import HasRichText, RichTextField

    class Post(HasRichText, BaseModel):
        body = RichTextField(attachment_cls=Attachment)

**The mixin must be listed before the model class.** Peewee's
`Model.save()` and `Model.delete_instance()` do not call `super()`, so a
mixin placed after the model in the bases is never reached: its hooks
would silently not run, embedded attachments would have no references,
and the abandoned-uploads sweeper would eventually delete them. To make
that mistake impossible to miss, declaring the bases in the wrong order
raises a `TypeError` when the class is defined.

A row deleted with a query (`Model.delete()`) or by the database (an
`ON DELETE CASCADE`) doesn't run the hooks. Call
`release_rich_text_attachments()` before a deletion by query, and
`rebuild_rich_text_references()` to repair the references of a model
after the fact.
"""
import typing as t

import peewee as pw

from .document import _collect_attachment_ids as _collect_ids_from_html


if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from ..storage import _Attachment


# `{attachment_cls: {attachment_id, ...}}`
TRemovedIds: t.TypeAlias = "dict[type[_Attachment], set[str]]"


def _iter_rich_text_fields(cls: type) -> "Iterator[tuple[str, pw.Field]]":
    """Yield `(field_name, field)` for every RichTextField column.

    Detected by duck-typing on the `attachment_cls` attribute, which
    every field built by `make_rich_text_field` carries. Using a
    structural check rather than `isinstance` lets users build
    alternative parents (compressed text, typed envelopes, etc.) via
    the factory without losing lifecycle support.
    """
    for name, field in cls._meta.fields.items():  # type: ignore
        if hasattr(field, "attachment_cls"):
            yield name, field


def _html_of(value: t.Any) -> str:
    """Coerce a field value (`str`, `RichTextDocument`, or `None`) to a
    plain HTML string. `None` becomes empty so collectors are no-ops.
    """
    if value is None:
        return ""
    if hasattr(value, "to_html"):
        return value.to_html()
    if isinstance(value, str):
        return value
    return ""


def _collect_attachment_ids(value: t.Any) -> list[str]:
    """Return attachment IDs in document order, deduped.

    Accepts the raw field value (`str` HTML, `RichTextDocument`, or
    `None`) and delegates to the HTML parser in `document.py`.
    """
    return _collect_ids_from_html(_html_of(value))


def _attachment_classes(cls: type) -> "set[type[_Attachment]]":
    """The attachment classes of the RichTextField columns of a model."""
    return {
        field.attachment_cls  # type: ignore
        for _name, field in _iter_rich_text_fields(cls)
        if field.attachment_cls is not None  # type: ignore
    }


def _purge_unreferenced(removed: TRemovedIds) -> None:
    """Schedule the purge of the attachments, among the ones given, that
    no record references anymore.
    """
    for attachment_cls, ids in removed.items():
        Reference = attachment_cls.Reference
        still_referenced = {
            row.attachment_id
            for row in Reference.select(Reference.attachment)
            .where(Reference.attachment.in_(ids))  # type: ignore
            .distinct()
        }
        gone = ids - still_referenced
        if not gone:
            continue
        for att in attachment_cls.select().where(attachment_cls.id.in_(gone)):  # type: ignore
            att.purge_later()


class HasRichText:
    """Mixin that handles RichTextField attachment lifecycle.

    Must come before the model class in the bases:
    `class Post(HasRichText, BaseModel)`.
    """

    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        mro = cls.__mro__
        if pw.Model in mro and mro.index(HasRichText) > mro.index(pw.Model):
            raise TypeError(
                f"`HasRichText` must be listed before the model class in the "
                f"bases of `{cls.__name__}`, e.g. "
                f"`class {cls.__name__}(HasRichText, BaseModel)`. "
                "Peewee's `Model.save()` and `Model.delete_instance()` don't "
                "call `super()`, so in the current order the mixin's hooks "
                "would never run and embedded attachments would be purged "
                "as abandoned uploads."
            )

    def save(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        database = type(self)._meta.database  # type: ignore
        with database.atomic():
            result = super().save(*args, **kwargs)  # type: ignore
            removed = self._sync_rich_text_references()
        # The purges are queued after the transaction, so that a failed
        # save doesn't purge an attachment that a record still embeds.
        _purge_unreferenced(removed)
        return result

    def delete_instance(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        database = type(self)._meta.database  # type: ignore
        with database.atomic():
            result = super().delete_instance(*args, **kwargs)  # type: ignore
            removed = self._remove_rich_text_references()
        _purge_unreferenced(removed)
        return result

    def release_rich_text_attachments(self) -> None:
        """Remove every reference of this record to its attachments, and
        schedule the purge of the ones that no other record embeds.

        `delete_instance()` does it. Call it yourself before deleting the
        record with a query, which doesn't run the hooks:

        ```python
        post.release_rich_text_attachments()
        Post.delete().where(Post.id == post.id).execute()
        ```
        """
        _purge_unreferenced(self._remove_rich_text_references())

    # Private

    def _rich_text_record(self) -> tuple[str, str]:
        cls = type(self)
        return cls._meta.table_name, str(self.get_id())  # type: ignore

    def _sync_rich_text_references(self) -> TRemovedIds:
        """Make the references of this record match the attachments
        embedded in each of its rich text columns. Return the ids of the
        attachments that this record stopped referencing, by attachment
        class, so the caller can purge the ones left without references.
        """
        cls = type(self)
        record_type, record_id = self._rich_text_record()
        removed: TRemovedIds = {}

        for name, field in _iter_rich_text_fields(cls):
            attachment_cls = field.attachment_cls  # type: ignore
            if attachment_cls is None:
                continue
            Reference = attachment_cls.Reference
            where = (
                (Reference.record_type == record_type)
                & (Reference.record_id == record_id)
                & (Reference.field == name)
            )
            new_ids = set(_collect_attachment_ids(getattr(self, name)))
            old_ids = {
                row.attachment_id
                for row in Reference.select(Reference.attachment).where(where)
            }

            gone = old_ids - new_ids
            if gone:
                Reference.delete().where(
                    where & Reference.attachment.in_(gone)
                ).execute()
                removed.setdefault(attachment_cls, set()).update(gone)

            added = new_ids - old_ids
            if added:
                # A body can name an attachment that doesn't exist (a stale
                # placeholder); the embed renders empty and gets no reference.
                existing = {
                    row.id
                    for row in attachment_cls.select(attachment_cls.id).where(
                        attachment_cls.id.in_(added)
                    )
                }
                if existing:
                    Reference.bulk_create([
                        Reference(
                            attachment=att_id,
                            record_type=record_type,
                            record_id=record_id,
                            field=name,
                        )
                        for att_id in sorted(existing)
                    ])

        return removed

    def _remove_rich_text_references(self) -> TRemovedIds:
        """Delete every reference of this record. Return the ids of the
        attachments it referenced, by attachment class.
        """
        record_type, record_id = self._rich_text_record()
        removed: TRemovedIds = {}

        for attachment_cls in _attachment_classes(type(self)):
            Reference = attachment_cls.Reference
            where = (
                (Reference.record_type == record_type)
                & (Reference.record_id == record_id)
            )
            ids = {
                row.attachment_id
                for row in Reference.select(Reference.attachment).where(where)
            }
            if ids:
                Reference.delete().where(where).execute()
                removed[attachment_cls] = ids

        return removed


def rebuild_rich_text_references(*models: type) -> None:
    """Make the attachment references of these models match what their
    rich text columns embed today.

    For each model: the references of rows that no longer exist are
    removed, and the references of every existing row are synced with
    its bodies. Nothing is purged: an attachment left without references
    is swept by `purge_abandoned_uploads()` once it is older than the
    grace period.

    Use it to fill the references of an app that has rich text records
    from before the table existed, from a data migration:

    ```python
    from proper.rich_text import rebuild_rich_text_references
    from myapp.models import Comment, Post

    def migrate(migrator, database, *, fake=False):
        migrator.run(rebuild_rich_text_references, Post, Comment)
    ```

    And to repair the references after deleting rows with a query or by
    an `ON DELETE CASCADE`, which don't run the hooks of `HasRichText`.
    """
    for model in models:
        record_type = model._meta.table_name  # type: ignore
        pk = model._meta.primary_key  # type: ignore
        existing_ids = {str(row[0]) for row in model.select(pk).tuples()}  # type: ignore

        for attachment_cls in _attachment_classes(model):
            Reference = attachment_cls.Reference
            referenced_ids = {
                row.record_id
                for row in Reference.select(Reference.record_id)
                .where(Reference.record_type == record_type)
                .distinct()
            }
            orphans = referenced_ids - existing_ids
            if orphans:
                Reference.delete().where(
                    (Reference.record_type == record_type)
                    & Reference.record_id.in_(orphans)  # type: ignore
                ).execute()

        for row in model.select().iterator():  # type: ignore
            row._sync_rich_text_references()
