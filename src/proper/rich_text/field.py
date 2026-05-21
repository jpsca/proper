"""`RichTextField` - Peewee model field for storing rich text documents.

A thin wrapper over `JSONField` that hydrates the raw dict into a
`RichTextDocument` on read.

Intentionally does *not* validate the AST on write. If callers want to ensure
structural validity before persisting, they should validate at the boundary
(a form field, an API deserializer) where the user can see and fix the error.

The parent used (`proper.models.JSONField` by default) can be swapped out if you
want to store the document in a different way (e.g. Postgres's native JSON type).
Use `make_rich_text_field` to create a new field class with the desired parent:

```python
from playhouse.postgres_ext import JSONField
from proper.rich_text import make_rich_text_field

RichTextField = make_rich_text_field(JSONField)
```
"""
import typing as t

import peewee as pw

from ..models import JSONField
from .document import RichTextDocument


if t.TYPE_CHECKING:
    from ..types import TAttachment


def make_rich_text_field(parent_cls: t.Any) -> type[pw.Field]:
    class RichTextField(parent_cls):
        """Peewee field storing a rich text document.

        Arguments:
            attachment_cls:
                The user's `Attachment` model class.
                Passed through to every `RichTextDocument` so it knows how
                to pre-fetch referenced embeds at render time.
                Leave as `None` if the documents will never embed
                attachments (e.g. plain rich text without files);
                embeds in that case render as empty.
            **kwargs:
                Forwarded to the parent field class
                (e.g.: `null`, `default`, `index`, etc.).
        """

        def __init__(
            self,
            attachment_cls: "type[TAttachment] | None" = None,
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
                value = value.to_dict()
            return super().db_value(value)

    return RichTextField


RichTextField = make_rich_text_field(JSONField)
