"""`RichTextField` - Peewee model field for storing rich text documents.

A thin wrapper over `TextField` that hydrates the raw HTML string into a
`RichTextDocument` on read.

Intentionally does *not* validate the HTML on write. If callers want to ensure
structural validity before persisting, they should validate at the boundary
(a form field, an API deserializer) where the user can see and fix the error.

The parent used (`peewee.TextField` by default) can be swapped out if you
want to store the document in a different way (e.g. Postgres's native `text`
column with a length cap, or a compressed column type).
Use `make_rich_text_field` to create a new field class with the desired parent:

```python
from playhouse.postgres_ext import TSVectorField
from proper.rich_text import make_rich_text_field

RichTextField = make_rich_text_field(TSVectorField)
```
"""
import typing as t

import peewee as pw

from .document import RichTextDocument


if t.TYPE_CHECKING:
    from ..types import TAttachment


class _RichTextFieldMixin(pw.Field):
    """Peewee field storing a rich text document as HTML.

    Arguments:
        attachment_cls:
            The user's `Attachment` model class.
            Passed through to every `RichTextDocument` so it knows how
            to pre-fetch referenced embeds at render time.
            Use `None` if the documents will never embed
            attachments (e.g. plain rich text without files);
            embeds in that case render as empty.
        **kwargs:
            Forwarded to the parent field class
            (e.g.: `null`, `default`, `index`, etc.).
    """

    def __init__(
        self,
        attachment_cls: "type[TAttachment] | None",
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.attachment_cls = attachment_cls

    def python_value(self, value: t.Any) -> RichTextDocument | None:
        data = super().python_value(value)
        if data is None:
            return None
        return RichTextDocument(data, attachment_cls=self.attachment_cls)

    def db_value(self, value: t.Any) -> t.Any:
        if isinstance(value, RichTextDocument):
            value = value.to_html()
        return super().db_value(value)


class RichTextField(_RichTextFieldMixin, pw.TextField):
    """Peewee field storing a rich text document as HTML."""


def make_rich_text_field(parent_cls: t.Any) -> type[pw.Field]:
    """Factory for creating a `RichTextField` subclass with a different parent.
    This is useful if you want to store the document in a different way
    (e.g. a compressed column, a typed JSON column for an HTML+metadata
    envelope) or if you want to add additional arguments to the constructor."""
    class RichTextField(_RichTextFieldMixin, parent_cls): ...
    return RichTextField
