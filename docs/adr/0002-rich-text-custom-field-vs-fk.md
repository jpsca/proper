# ADR-0002: Rich Text is a Peewee Field, not a Foreign Key

**Status:** Accepted (2026-05-21)


## Context

Where does the body of a rich text field live in the schema?

- **As a foreign key to a separate `rich_text` table.** This is what
  Action Text does (`Post → ActionText::RichText → ActiveStorage::Blob`).
- **As a JSON column on the parent model**, with the body sitting next
  to the rest of the parent's fields. The Peewee field hydrates the
  JSON into a `RichTextDocument` on read.

The choice affects ergonomics, indirection cost, and how natural it
feels to read the parent model's declaration.


## Decision

Make it a custom Peewee field - a `RichTextField` extending Peewee's
`JSONField`. The body is a JSON column on the parent model:

```python
class Post(HasRichText, BaseModel):
    title = pw.CharField(max_length=200)
    body = RichTextField(attachment_cls=Attachment)
```


## Consequences

- The model reads naturally: `body` looks like any other field. No
  separate table, no JOIN, no second migration.
- Multiple rich-text fields per model are supported by declaring more
  columns - `body`, `summary`, etc. The `HasRichText` mixin discovers
  them all via `_meta.fields` and reconciles attachments across every
  one on save and delete.
- The field is built by a `make_rich_text_field(parent_cls)` factory,
  so the backing column type can be swapped without forking the
  module (Postgres-native `jsonb` via `playhouse.postgres_ext.JSONField`,
  for instance).
- Attachment lifecycle (purging removed embeds, marking surviving ones
  as confirmed) sits in the `HasRichText` mixin's `save` and
  `delete_instance` overrides. The mixin auto-discovers Rich Text
  Fields by walking `cls._meta.fields` - no declarative list on the
  model.


## Alternatives considered

- **Foreign key to a separate `rich_text` table.** Rejected because
  Proper already has `Attachment` as a standalone model; embedding
  attachments inside a `RichText` row pointed at by `Post` adds a
  third indirection layer (`Post → RichText → Attachment`) that buys
  nothing. The body fits comfortably in a single JSON column. Rails
  needed the separate table because its embedded attachments were
  `ActiveStorage::Blob`s, and Action Text didn't want to depend on
  Active Storage for the table existence; we don't have that
  constraint.
- **Inline (TextField on the parent).** Rejected because the JSON
  needs structured access at the Python level (the renderer walks the
  AST, the `HasRichText` mixin diffs old vs new IDs, plain-text
  extraction walks the same tree). A plain `TextField` would force
  every consumer to parse JSON manually.
