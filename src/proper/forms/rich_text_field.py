"""Form-layer field for rich text bodies.

`RichTextFormField` is a thin subclass of `formidable.TextField` that
knows how to coerce a `RichTextDocument` (the runtime value of a
`RichTextField` model column) into the HTML string the form needs to
render and submit.

Without this adapter, loading an existing record into the form would
hit `str(RichTextDocument)` — which returns plain text — and the editor
would re-load the post body as a flat paragraph of plain text instead
of the original HTML.
"""
import typing as t

from formidable.fields import TextField

from ..rich_text.document import RichTextDocument


class RichTextField(TextField):
    """A `TextField` that accepts `RichTextDocument` values from a model
    instance and renders them as HTML.
    """

    def __init__(self, *, required: bool = False, **kwargs: t.Any) -> None:
        # Rich text bodies are usually optional — most pages allow an
        # empty document. The base default is `required=True`; flip it.
        super().__init__(required=required, strip=False, **kwargs)

    def filter_value(self, value: t.Any) -> str | None:
        if isinstance(value, RichTextDocument):
            value = value.to_html()
        return super().filter_value(value)
