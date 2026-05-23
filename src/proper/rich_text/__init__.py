"""Rich text document support - storage, rendering, and helpers.

The runtime value of a `RichTextField` is a `RichTextDocument`: a
small wrapper over an HTML string produced by the editor (Lexxy). The
document knows how to expand `<proper-attachment>` placeholders into the
`RichTextAttachment` partial (for templates) and how to flatten the
HTML to plain text (for search, previews, OG tags).

For attachment lifecycle (purging removed embeds, marking surviving
ones as confirmed, sweeping abandoned uploads), mix `HasRichText`
into the parent model and run `purge_abandoned_uploads` periodically
from a Huey task.
"""
from .concerns import HasRichText
from .document import RichTextDocument
from .field import RichTextField, make_rich_text_field
from .tasks import purge_abandoned_uploads


__all__ = (
    "HasRichText",
    "RichTextDocument",
    "RichTextField",
    "make_rich_text_field",
    "purge_abandoned_uploads",
)
