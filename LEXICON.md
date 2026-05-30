# Lexicon

Project-wide glossary. Each term has one precise meaning here — when
writing internals, docs, or commit messages, use these.

The lexicon grows on demand: only terms whose meaning could otherwise
drift (because they overlap with everyday English, or because different
parts of the codebase might call the same thing different names) get an
entry.


## Attachment

A row in the `attachment` table that records the metadata of a stored
file (filename, content type, byte size, the service that holds the
bytes) plus two lifecycle columns:

- **source** — where the upload came from. `"direct"` for files
  submitted as part of a form; `"rich_text"` for files uploaded by the
  editor before the surrounding form is submitted. Open to extension
  for other upload mechanisms (API, email import, etc.).
- **pending** — `True` when the upload exists but no parent record has
  confirmed ownership yet. Flips to `False` when a `HasRichText` save
  finds the attachment referenced in a body. Rows that stay pending
  past a grace period are purged by a periodic sweep.

The `Attachment` model lives in the storage addon. Other models
reference it through a regular `ForeignKeyField` (form-submitted
uploads) or by ID inside a Rich Text Document (editor-embedded
uploads).


## Rich Text Document

The AST-shaped JSON value stored by a Rich Text Field. A tree of nodes
following the ProseMirror schema, with `{type, attrs?, content?,
marks?, text?}` shapes.

At runtime, the value is a `RichTextDocument` Python object:

- `__html__()` renders the document to HTML (used implicitly by Jinja
  whenever the document is interpolated into a template).
- `__str__()` renders to plain text — suitable for search indices,
  email previews, OG meta tags.
- `.attachments` is the list of `Attachment` rows referenced by the
  document, pre-fetched in a single batched query.


## Rich Text Field

A Peewee field whose column type is JSON and whose Python value is a
Rich Text Document.

Built by the `make_rich_text_field(parent_cls)` factory so the backing
column type can be swapped (`proper.models.JSONField` by default) to
`playhouse.postgres_ext.JSONField` for Postgres-native `jsonb`, or any
other JSON-shaped Peewee field.

The model field intentionally does **no** validation: validation
belongs at form boundaries, not at the persistence layer. Models that
declare one or more Rich Text Fields should also mix in `HasRichText`,
which adds the `save`/`delete_instance` hooks that keep referenced
attachments in sync with the document.


## Attachment Embed

An `attachment`-type node inside a Rich Text Document, referencing an
`Attachment` row by UUID. The on-the-wire shape is:

```json
{
  "type": "attachment",
  "attrs": {
    "id": "<uuid>",
    "alt": "...",
    "caption": "...",
    "url": "...",
    "content_type": "..."
  }
}
```

`alt` and `caption` are per-embed user-editable text — the same
`Attachment` can be embedded in two different documents with different
captions.

`url` and `content_type` are render hints the editor uses to draw the
embed live without an extra network round-trip. The server-side
renderer ignores them and uses the resolved `Attachment` row instead,
so they can safely drift.
