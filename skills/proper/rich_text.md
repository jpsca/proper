---
title: Rich Text
description: Rich Text addon — formatted-text field with embedded attachments, Lexxy editor, attachment lifecycle
last_verified: 2026-05-29
---

# Proper Rich Text

Proper Rich Text is an installable addon that stores formatted documents (bold, italics, lists, tables, hyperlinks, embedded images/files) and ships a default browser editor — [Lexxy](https://basecamp.github.io/lexxy/) — that knows how to produce and edit them.

Rich Text **depends on** the [Storage addon](storage.md): every embedded file is an `Attachment` row, and rich-text attachments use Storage's [direct upload](storage.md#direct-uploads) flow so the editor uploads files *before* the parent form is submitted. Read the Storage doc first if you haven't met the `Attachment` model.

## Table of Contents

- [Setup](#setup)
- [Adding Rich Text to a Model](#adding-rich-text-to-a-model)
- [Rendering Rich Text](#rendering-rich-text)
- [The Editor Component](#the-editor-component)
- [Customizing the Toolbar](#customizing-the-toolbar)
- [Extending the Editor with Prompts](#extending-the-editor-with-prompts)
- [Attachment Lifecycle](#attachment-lifecycle)
- [Sweeping Abandoned Uploads](#sweeping-abandoned-uploads)
- [Working with Documents from Python](#working-with-documents-from-python)
- [Custom Storage for the Document](#custom-storage-for-the-document)

## Setup

Install the rich_text blueprint with:

```bash
proper install rich_text
proper db migrate
```

This:

- Installs the [Storage addon](storage.md) if it isn't already (needed for attachments).
- Adds the Lexxy editor (JS + CSS) into your assets.
- Creates three Jx components: `rich_text_editor.jx`, `rich_text_toolbar.jx`, and `rich_text_attachment.jx`.
- Adds a periodic task at `tasks/abandoned_uploads_sweep.tt.py` for cleaning up abandoned pre-uploads.

The migration is for the `attachment` table added by the storage addon — rich_text itself doesn't add or change columns. The field stores the HTML on whatever text column you already have.

## Adding Rich Text to a Model

Rich text works on top of an existing text column — no migration needed to convert one. Update the column type and (when embedding attachments) add the `HasRichText` mixin:

```python
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .attachment import Attachment
from .base import BaseModel


# BaseModel always goes first.
class Post(BaseModel, HasRichText):
    title = pw.CharField()
    body = RichTextField(Attachment, null=True)
```

The first positional argument to `RichTextField` is the `Attachment` model — the document needs it to resolve embedded references at render time.

If a particular column will never embed images or files, pass `None` and drop the mixin:

```python
class Post(BaseModel):
    title = pw.CharField()
    body = RichTextField(None, null=True)
```

`HasRichText` auto-discovers every `RichTextField` column on the model (by looking for fields with an `attachment_cls` attribute), so one mixin handles all of them — no declarative list, no extra configuration. A model can have multiple rich-text columns and the lifecycle treats each one independently.

### The form field

Use `f.RichTextField` (a thin subclass of `f.TextField`) on the matching form:

```python
from proper import forms as f

from [[app_name]].models import Post


class PostForm(f.Form):
    class Meta:
        orm_cls = Post

    title = f.TextField()
    body = f.RichTextField(required=False)
```

The form field knows to coerce a `RichTextDocument` (the runtime value of the model column) into the HTML string the editor expects. `required` defaults to `False` here — rich-text bodies are usually optional.

## Rendering Rich Text

`RichTextDocument` is `Markup`-safe: drop it into a template and it renders sanitized HTML, with embedded `<proper-attachment>` placeholders expanded via the `rich_text_attachment.jx` component:

```html+jinja
{{ post.body }}
```

`__html__()` returns the HTML. `__str__()` returns plain text (paragraph breaks, list bullets, alt text for embeds) — useful for OG tags, search indices, email previews.

For visual parity with the editor, include `lexxy-content.css` and wrap the content in a `lexxy-content` element:

```html+jinja
{#css css/lexxy-content.css #}

<div class="lexxy-content">
  {{ post.body }}
</div>
```

### How attachment embeds render

Stored HTML uses `<proper-attachment sgid="..." caption="..."></proper-attachment>` placeholders instead of `<img>` tags. On render, the document collects all referenced UUIDs, fetches the rows in a single query (no N+1), and renders each one through `views/rich_text_attachment.jx`. The component receives:

- `attachment` — the resolved `Attachment` row
- `alt`, `caption` — text the user typed for this embed
- any other attribute the editor wrote on the placeholder tag

Edit `rich_text_attachment.jx` to customise rendering — e.g. videos via `<video>`, smaller image variants, fallback download link:

```html+jinja
{#def attachment, alt: str = "", caption: str = "" #}

{% if attachment.content_type.startswith("video/") %}
  <video controls src="{{ attachment.url }}"></video>
{% elif attachment.is_previewable %}
  {% set variant = attachment.variant(resize_to_limit=(800, 800)) %}
  <figure>
    <img src="{{ variant.url }}" alt="{{ alt }}" loading="lazy">
    {% if caption %}<figcaption>{{ caption }}</figcaption>{% endif %}
  </figure>
{% else %}
  <a href="{{ attachment.url }}">{{ attachment.filename }}</a>
{% endif %}
```

> **Heads up:** the default `rich_text_attachment.jx` calls `attachment.variant(resize_to_limit=(1600, 1600))` for previewable content. Make sure `VARIANTS_ENABLED_FOR["image/*"] = "preview_image"` is enabled on your `Attachment` model (the storage blueprint enables it by default) and `pyvips` + `libvips` are installed. See [storage.md#variants](storage.md#variants).

## The Editor Component

The blueprint installs `views/rich_text_editor.jx`. Use it in your form view:

```html+jinja
{#import "form.jx" as Form #}
{#import "rich_text_editor.jx" as RichTextEditor #}

<Form method="post" action={{ action }}>
  <div class="field">
    {{ form.title.label("Title") }}
    {{ form.title.text_input() }}
    {{ form.title.error_tag() }}
  </div>
  <div class="field">
    {{ form.body.label("Body") }}
    <RichTextEditor field={{ form.body }}></RichTextEditor>
    {{ form.body.error_tag() }}
  </div>
</Form>
```

Editor options (all are HTML attributes on `<RichTextEditor>`; values are strings):

Option           | Description
---------------- | --------------------------
`toolbar`        | `"false"` to disable the toolbar entirely. Default renders `rich_text_toolbar.jx`.
`toolbar-upload` | Which upload button(s) appear: `"file"`, `"image"`, or `"both"` (default). The image button restricts the file picker to `image/*,video/*` (which triggers the native photo/video picker on iOS/Android). The file button is unrestricted.
`attachments`    | `"false"` disables attachments completely (including drag-and-drop and paste).
`permitted-attachment-types` | Space-separated allowlist of content types, e.g. `"application/epub+zip application/pdf"`. Unset = anything.
`markdown`       | `"true"` to enable Markdown shortcuts.
`multi-line`     | `"false"` to force single-line editing.
`upload_url`     | Override the direct-upload endpoint per-form. Defaults to `url_for("DirectUpload.create")`. Useful for membership-gated uploads.

The editor also accepts standard HTML attributes: `placeholder`, `class`, `disabled`, `autofocus`.

Under the hood the component:

- POSTs blob metadata to `DirectUpload.create` (the storage addon's controller) on each new file.
- Substitutes `:signed_id` / `:filename` into the redirect URL template so embedded attachments display in the editor exactly as they will on the published page.

## Customizing the Toolbar

The toolbar is `views/rich_text_toolbar.jx` — edit classes, swap icons, add or remove buttons.

Removing a button doesn't remove the format itself:

- Drag-and-drop / paste still uploads files (use `attachments="false"` on the editor to disable).
- Keyboard shortcuts still work: `Ctrl+B` (bold), `Ctrl+I` (italics), `Ctrl+K` (link), etc.

## Extending the Editor with Prompts

"Prompts" are Lexxy's mechanism for trigger-based suggestions (`@mentions`, `/commands`, emoji pickers, etc.). Triggered by typing a configured character, they show a menu of items the user can select.

Two flavours:

- **Insert as free editable text** — add the `insert-editable-text` attribute to `<lexxy-prompt>`. The selected `<template type="editor">` content is inserted as plain editable HTML. Good for emojis, hashtags, anything inline that doesn't need server-side processing.
- **Insert as a custom attachment** — selecting an item inserts a `<proper-attachment>` placeholder pointing at a row you create server-side, then renders through your custom partial. Good for `@mentions` (link to a user), `/commands` (interactive blocks), etc.

Example: an emoji picker triggered by `:`:

```html
<RichTextEditor field={{post.body}}>
  <lexxy-prompt trigger=":" insert-editable-text>
    <lexxy-prompt-item search="joy laughing face">
      <template type="menu">😂 :joy</template>
      <template type="editor">😂</template>
    </lexxy-prompt-item>
    <lexxy-prompt-item search="heart red">
      <template type="menu">❤️ :heart</template>
      <template type="editor">❤️</template>
    </lexxy-prompt-item>
  </lexxy-prompt>
</RichTextEditor>
```

Lexxy also lets you load items inline or remotely, and filter locally or server-side — see Lexxy's docs for the full API.

## Attachment Lifecycle

The editor uploads each file the moment the user drops it in — **before** the form is submitted. This sets up an interesting reconciliation problem: until the parent form is saved, the attachment is provisional. The user might close the tab.

The flow:

1. User drops a file → browser POSTs metadata to `DirectUpload.create`.
2. Server creates an `Attachment` row with `source="direct"` and `pending=True`, returns a signed URL.
3. Browser PUTs the bytes directly to storage (S3) or to `DirectUpload.update` (Disk).
4. Editor inserts `<proper-attachment sgid="...">` into the document.
5. User submits the form → parent model's `save()` runs.

`HasRichText` hooks `save()` and `delete_instance()` to keep the database honest:

**On save**, for every rich-text column:

- Diffs the **new body** against the **prior body** (loaded fresh by PK).
- Marks every attachment still referenced as `pending=False` (single batched UPDATE).
- Schedules `purge_later()` for every attachment that *was* in the prior body but no longer appears.

**On delete**, for every rich-text column:

- Collects all referenced attachment IDs *before* the parent row is deleted.
- Schedules `purge_later()` for each one after the parent row is gone.

All purges go through Huey, so they don't block the save or the user's request.

If a model holds rich text but **should not** own its attachments (e.g. they're shared between records), don't include `HasRichText`. Rendering still works; only the automatic cleanup is opted out.

## Sweeping Abandoned Uploads

Pre-uploaded files that never get confirmed are orphans — bytes in storage with no document pointing at them. The blueprint generates a periodic task at `tasks/abandoned_uploads_sweep.tt.py`:

```python
from huey import crontab
from proper.rich_text import purge_abandoned_uploads

from [[app_name]].main import app
from [[app_name]].models import Attachment


@app.queue.periodic_task(crontab(hour="3", minute="0"))
def sweep_abandoned_uploads():
    purge_abandoned_uploads(Attachment, grace_hours=24)
```

`purge_abandoned_uploads(attachment_cls, *, grace_hours=24, source="direct")` queries for rows where `source == source AND pending == True AND created_at < now - grace_hours` and calls `purge_later()` on each. Returns the count of rows scheduled.

- A **short** `grace_hours` reclaims storage faster but risks deleting an upload while the user is still composing a long post.
- A **long** `grace_hours` is gentler on users but keeps orphans around longer.

The sweep only touches rows where `source` matches — other addons that pre-upload with their own lifecycle policy (and their own `source` value) aren't affected.

## Working with Documents from Python

A `RichTextDocument` exposes the attachments it references:

```python
post = Post.get(slug="my-post")

for att in post.body.attachments:
    print(att.filename, att.content_type, att.byte_size)
```

The list is loaded lazily on first access and cached for the lifetime of the document instance, so reading `.attachments` more than once does **not** re-hit the database.

Useful for: building a gallery of every image in a post, picking a thumbnail for an OpenGraph tag, feeding attachment metadata into an external search index.

Equality compares the underlying HTML:

```python
post.body == "<p>Hello</p>"
post.body == other_post.body
```

`document.to_html()` returns the raw HTML string (useful for serialization, dumping into a JSON API response).

## Custom Storage for the Document

`RichTextField` is `_RichTextFieldMixin + peewee.TextField` by default. If you want to store the document in a different column type — Postgres `TSVectorField`, a compressed column, a typed JSON envelope — use `make_rich_text_field`:

```python
from playhouse.postgres_ext import TSVectorField
from proper.rich_text import make_rich_text_field

RichTextField = make_rich_text_field(TSVectorField)
```

The mixin handles `python_value` (hydrate HTML → `RichTextDocument`) and `db_value` (serialize `RichTextDocument` → HTML), while the parent class handles the actual column type.

The mixin is detected by `HasRichText` via a structural check on the `attachment_cls` attribute, so a custom parent still participates in lifecycle reconciliation automatically — no extra plumbing needed.
