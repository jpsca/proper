---
title: Rich Text
description: Rich Text addon — formatted-text field with embedded attachments, Lexxy editor, attachment lifecycle
last_verified: 2026-11-07
sources:
  - src/proper/rich_text
  - src/proper/_blueprints/addon_rich_text
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
- Adds a periodic task at `tasks/abandoned_uploads_sweep.py` for cleaning up abandoned pre-uploads, imported from `tasks/__init__.py` so Huey registers it.
- Adds the Lexxy editor to your assets (`js/vendor/lexxy.js`, `js/vendor/lexxy-helpers.js`, `js/lexxy-config.js`, `css/lexxy-editor.css`, `css/lexxy-content.css`, `css/lexxy-variables.css`) and the `lexxy` entry to `config/import_map.py`. The vendored `lexxy.js` loads `@rails/activestorage` from `esm.sh` at runtime, so the page needs network and CSP access to that host.
- Adds `config/rich_text.py` (the allowlists of the [sanitizer](#sanitizing)), imports it from `config/__init__.py`, and adds the `nh3` dependency.

The migration is for the `attachment` and `attachment_reference` tables added by the storage addon — rich_text itself doesn't add or change columns. The field stores the HTML on whatever text column you already have.

## Adding Rich Text to a Model

Rich text works on top of an existing text column — no migration needed to convert one. Update the column type and (when embedding attachments) add the `HasRichText` mixin:

```python
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .attachment import Attachment
from .base import BaseModel


# HasRichText MUST go before BaseModel. Peewee's `save()` doesn't call
# `super()`, so in the other order the mixin would never run
# (Proper raises a TypeError if you get it wrong).
class Post(HasRichText, BaseModel):
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

from myapp.models import Post


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

`__html__()` returns the sanitized HTML. `__str__()` returns plain text, by the same rules as `proper.helpers.html2text` (the text of HTML emails): blank lines between blocks, `- ` list items, `text (href)` links, `[alt]` for images, `[alt]`/`[caption]`/`[filename]`/`[file]` for attachments, three backticks around `<pre>` — useful for OG tags, search indices, email previews.

For visual parity with the editor, include `lexxy-content.css` and wrap the content in a `lexxy-content` element:

```html+jinja
{#css css/lexxy-content.css #}

<div class="lexxy-content">
  {{ post.body }}
</div>
```

### Sanitizing

The stored HTML is whatever the form sent; it is sanitized with `nh3` **every time it is rendered** (`__html__`), never on save. The allowlist is in `config/rich_text.py` (installed by the addon, which also adds `nh3` to the dependencies):

| Setting                         | Description                                                          |
|---------------------------------|----------------------------------------------------------------------|
| `RICH_TEXT_SANITIZE`            | `True`. `False` renders the stored HTML as is (trusted authors only) |
| `RICH_TEXT_ALLOWED_TAGS`        | List of tags                                                         |
| `RICH_TEXT_ALLOWED_ATTRIBUTES`  | Dict of tag -> list of attributes; `"*"` applies to every tag        |
| `RICH_TEXT_ALLOWED_STYLES`      | CSS properties kept in `style` attributes                            |
| `RICH_TEXT_ALLOWED_URL_SCHEMES` | URL schemes for `href`/`src`; relative URLs are always allowed       |

- If the editor is extended to write other tags or attributes, add them to the lists or they won't be rendered. The attributes kept on `<proper-attachment>` are a fixed list (`proper.rich_text.sanitizer.ATTACHMENT_ATTRIBUTES`: `alt`, `caption`, `content`, `content-type`, `filename`, `filesize`, `height`, `presentation`, `previewable`, `sgid`, `url`, `width`) that `RICH_TEXT_ALLOWED_ATTRIBUTES` doesn't change.
- `<proper-attachment>` tags are always kept; the output of `rich_text_attachment.jx` is not sanitized.
- Never allow `data-controller` / `data-action`: a document could run the app's Stimulus controllers.
- `doc.to_html()` is the raw stored HTML (unsafe to render). `doc.to_safe_html()` is the sanitized HTML with the attachment tags still in place.
- Links get `rel="noopener noreferrer"` unless `rel` is an allowed attribute of `a` (or of `"*"`).
- Without `nh3` installed, rendering raises `ConfigError`.

### How attachment embeds render

Stored HTML uses `<proper-attachment sgid="..." caption="..."></proper-attachment>` placeholders instead of `<img>` tags. On render, the document collects all referenced UUIDs, fetches the rows in a single query (no N+1), and renders each one through `views/rich_text_attachment.jx`. The component receives:

- `attachment` — the resolved `Attachment` row
- `alt`, `caption` — text the user typed for this embed
- any other attribute the editor wrote on the placeholder tag, among the ones the sanitizer keeps on `<proper-attachment>` (see Sanitizing above)

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

> **Heads up:** the default `rich_text_attachment.jx` calls `attachment.variant(resize_to_limit=(1600, 1600))` for previewable content. Make sure `VARIANTS_ENABLED_FOR["image/*"] = "preview_image"` is enabled on your `Attachment` model (the storage blueprint enables it by default) and `pyvips` + `libvips` are installed. See [storage_advanced.md#variants](storage_advanced.md#variants).

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
- Keyboard shortcuts for text formats still work (`Ctrl+B`, `Ctrl+I`, ...). `Ctrl+K` (link) is a `data-hotkey` on the toolbar's link button, so it goes away with the button; `data-hotkey` works on any toolbar button.

## Extending the Editor with Prompts

"Prompts" are Lexxy's mechanism for trigger-based suggestions (`@mentions`, `/commands`, emoji pickers, etc.). Triggered by typing a configured character, they show a menu of items the user can select.

Two flavours:

- **Insert as free editable text** — add the `insert-editable-text` attribute to `<lexxy-prompt>`. The selected `<template type="editor">` content is inserted as plain editable HTML. Good for emojis, hashtags, anything inline that doesn't need server-side processing.
- Lexxy can also insert a prompt item as a `<proper-attachment>` with a custom `content-type` (`application/vnd.proper.<prompt-name>`) and the item's `sgid`. Proper's renderer resolves `sgid` only against the `Attachment` model and drops tags it can't resolve, so this flavour (`@mentions`, `/commands`) is not supported out of the box.

Example: an emoji picker triggered by `:`:

```html
<RichTextEditor field={{ form.body }}>
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

Proper keeps the records that embed each attachment in a table, `attachment_reference`: one row per `(record_type, record_id, field, attachment)`, where `record_type` is the table name of the model, `record_id` its primary key as a string and `field` the rich text column. The model is `Attachment.Reference`, built by `attachment_for()` and exported as `AttachmentReference` by the storage addon's `models/attachment.py` (so `proper db create` makes its table). Two records can embed the same attachment (a copied post, each version of a versioned document): it is purged only when its **last** reference goes away.

- `att.is_referenced` — whether some record embeds it.
- `att.references` — the reference rows (peewee backref).

The flow:

1. User drops a file → browser POSTs metadata to `DirectUpload.create`.
2. Server creates an `Attachment` row with `source="rich_text"` (the `source` class attribute of `DirectUploadController`) and no references, and returns its `signed_id`, its `url` and a `direct_upload` envelope (`url` + `headers`) telling the browser where to PUT the bytes.
3. Browser PUTs the bytes directly to storage (S3) or to `DirectUpload.update` (Disk).
4. Editor inserts `<proper-attachment sgid="...">` into the document.
5. User submits the form → parent model's `save()` runs.

`HasRichText` hooks `save()` and `delete_instance()` to keep the database honest:

**On save**, for every rich-text column, diffs the attachment ids of the **new body** against the **references** of the record for that column:

- Inserts a reference for each new id (ids of attachments that don't exist are skipped: the embed renders empty).
- Deletes the references of the ids that are gone, then schedules `purge_later()` for the ones that **no other record references**.

The save and the reference changes run in one transaction; the purges are queued after it.

**On delete**, deletes every reference of the record and schedules `purge_later()` for the attachments left without any.

All purges go through Huey, so they don't block the save or the user's request.

Deletions by query and by the database don't run the hooks:

- `record.release_rich_text_attachments()` — drops the references of the record and purges the attachments left without any. Call it **before** `Model.delete().where(...).execute()`.
- `rebuild_rich_text_references(*models)` (in `proper.rich_text`) — for each model, drops the references of rows that no longer exist and syncs the references of every row with its bodies. Purges nothing (the sweep handles unreferenced uploads). Use it from a data migration to fill the table for existing records (`migrator.run(rebuild_rich_text_references, Post, Comment)`), and to repair after `ON DELETE CASCADE` or `Model.update()` of a body.

Composite primary keys are not supported (`record_id` is one string).

## Sweeping Abandoned Uploads

Pre-uploaded files that no record ever embeds are orphans — bytes in storage with no document pointing at them. The installer generates `tasks/abandoned_uploads_sweep.py` (already imported from `tasks/__init__.py`):

```python
from huey import crontab
from proper.rich_text import purge_abandoned_uploads

from myapp.main import app
from myapp.models import Attachment


@app.queue.periodic_task(crontab(hour="3", minute="0"))
def sweep_abandoned_uploads():
    purge_abandoned_uploads(Attachment, grace_hours=24)
```

`purge_abandoned_uploads(attachment_cls, *, grace_hours=24, source="rich_text")` queries for rows where `source == source AND parent IS NULL AND created_at < now - grace_hours AND NOT EXISTS (reference)` and calls `purge_later()` on each. Returns the count of rows scheduled. Variants are skipped: they are purged with their parent.

- A **short** `grace_hours` reclaims storage faster but risks deleting an upload while the user is still composing a long post.
- A **long** `grace_hours` is gentler on users but keeps orphans around longer.

The sweep only touches rows where `source` matches. "Without references" means "unused" only for the editor's uploads: a file sent with a form or attached through a foreign key has an empty `source` and no references, and is in use, so it is never swept. Other addons that pre-upload with their own lifecycle policy (and their own `source` value) aren't affected either.

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

`document.to_html()` returns the raw stored HTML string (useful for serialization, dumping into a JSON API response).

`document.to_editor_html()` returns the HTML for the editor: the stored HTML with each `<proper-attachment>` tag re-hydrated from its row (`url`, `filename`, `content-type`, `filesize`, `previewable`). `f.RichTextField` uses it automatically.

### What is stored

Only `sgid` plus what the author typed (`alt`, `caption`, `presentation`, ...). The attributes derived from the attachment row (`proper.rich_text.document.DERIVED_ATTRS`) are stripped by `RichTextField.db_value` and rebuilt by `to_editor_html()`. The embed `url` is signed with `SECRET_KEYS`, so persisting it would break the editor's thumbnails whenever the database is copied to another environment or the keys are replaced. Consequences:

- Never build features on a stored `url`/`filename` attribute; read them from `document.attachments`.
- Documents saved by older versions still carry those attributes. No migration is needed: they are ignored on load and dropped on the next save.
- If you hand a document to an editor yourself (not through `f.RichTextField`), use `to_editor_html()`, not `to_html()`.

## Custom Storage for the Document

`RichTextField` is `_RichTextFieldMixin + peewee.TextField` by default. If you want to store the document in a different column type — Postgres `TSVectorField`, a compressed column, a typed JSON envelope — use `make_rich_text_field`:

```python
from playhouse.postgres_ext import TSVectorField
from proper.rich_text import make_rich_text_field

RichTextField = make_rich_text_field(TSVectorField)
```

The mixin handles `python_value` (hydrate HTML → `RichTextDocument`) and `db_value` (serialize `RichTextDocument` → HTML), while the parent class handles the actual column type.

The mixin is detected by `HasRichText` via a structural check on the `attachment_cls` attribute, so a custom parent still participates in lifecycle reconciliation automatically — no extra plumbing needed.
