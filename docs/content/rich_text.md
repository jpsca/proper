---
title: Rich Text
description: |
  How to store, render, and edit rich text content in Proper, including embedded image and file attachments. Covers the RichTextField, the bundled TipTap-based editor, attachment lifecycle, and how to customize or replace any piece.
number_headers: true
---

# Rich Text

This guide covers Proper's rich text addon - a field type that stores
formatted documents with embedded attachments, plus a default editor
that knows how to produce and edit them.

After reading this guide, you will know:

- What rich text means in Proper and how it differs from a plain text column.
- How to install the addon and add a body field to one of your models.
- How the bundled editor handles uploads, paste, and drag-and-drop.
- How to render rich text safely in templates, including plain-text extraction for previews.
- How to customize the look of embedded attachments.
- How attachment lifecycle is managed - and how the periodic sweep keeps abandoned uploads from accumulating.
- How to swap the editor for a different one (or none at all) and emit the storage format directly.

The companion [File Storage](/docs/storage) guide covers attachments at the level rich text builds on. Read it first if you haven't met the `Attachment` model.

---

## What is Rich Text?

Rich text in Proper is **structured content** - a tree of paragraphs, headings, lists, marks like bold and italic, and embedded attachments - stored as JSON in a single column on your model. It's what you reach for when a `CharField` is too narrow and a plain `TextField` is too unstructured (a blog post body, an article, a long comment with images).

The two pieces:

- **A storage format.** A document is a tree of nodes following the ProseMirror schema. Stored as JSON, kept as JSON until rendered. The runtime value is a `RichTextDocument` Python object that knows how to render itself to HTML and to plain text.
- **An editor.** The addon ships with a TipTap-based editor that produces and consumes that JSON. Vendored so your app works offline; replaceable if you want a different one.

```python
class Post(HasRichText, BaseModel):
    title = pw.CharField(max_length=200)
    body = RichTextField(attachment_cls=Attachment)
```

```jinja
{# In a template - emits HTML, attachments resolved automatically. #}
{{ post.body }}

{# Same document, plain text version - for OG tags, search, previews. #}
{{ post.body | striptags }}
```

The on-the-wire shape is a JSON tree like:

```json
{
  "type": "doc",
  "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "Hola"}]},
    {"type": "attachment", "attrs": {"id": "abc-123", "alt": "Mi gato"}}
  ]
}
```

You'll rarely look at this directly - the editor produces it, the renderer consumes it. But it's printable, diffable, and the framework's contract: any editor that emits this shape works with Proper's renderer.

---

## Setup

The rich text addon is installed on demand:

```bash
$ proper install rich_text
```

This:

- Adds `Attachment` lifecycle columns (`source`, `pending`) to the storage addon's model - autoinstalling storage if you haven't already.
- Writes the upload endpoint controller, the Jx components, the editor's JavaScript, the CSS, and a periodic sweep task into your app.
- Appends TipTap entries to `config/import_map.py`.
- Records itself in `.proper`, the file that tracks which addons live in your app (so dependencies can be resolved on the next install).

After the install runs the migration generator:

```bash
$ proper db migrate
```

:::note | The `.proper` file
The first addon you install creates a `.proper` JSON file at the root of your app. Commit it - it's how the framework knows which addons are present after a fresh clone, without needing the database to be reachable. Read more in [ADR-0003](/docs/adr/0003-proper-metadata-file).
:::

---

## Declaring a Rich Text Field on a Model

The minimum:

```python
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .attachment import Attachment
from .base import BaseModel


class Post(HasRichText, BaseModel):
    title = pw.CharField(max_length=200)
    body = RichTextField(attachment_cls=Attachment)
```

Two things to call out:

- **`attachment_cls=Attachment`** tells the field which `Attachment` class to pre-fetch from when rendering embedded files. The field carries it through to the `RichTextDocument` at read time so `__html__()` can resolve embeds in one batched query. If your documents will never embed files (e.g. plain rich text), you can leave it as `None`; embeds in that case render as empty.
- **`HasRichText`** is a mixin that auto-discovers every `RichTextField` on the model and adds lifecycle hooks: on save it diffs the body against the prior version and purges attachments that disappeared; on delete it purges every attachment the body references. The fields are discovered by walking `cls._meta.fields` - no declarative list to keep in sync.

Multiple rich-text fields on a single model work without ceremony:

```python
class Post(HasRichText, BaseModel):
    body = RichTextField(attachment_cls=Attachment)
    summary = RichTextField(attachment_cls=Attachment, null=True)
```

Both columns participate in lifecycle reconciliation.

:::tip | When NOT to mix in `HasRichText`
If a model has a `RichTextField` but the column is fully managed externally (e.g. a read-only mirror of another system's data), skip the mixin - you don't want the save hooks running. The column still works as a value object; you just opt out of the automatic attachment cleanup.
:::

---

## The Editor

The bundled editor is mounted via a Stimulus controller in a Jx component. In a form, render it like any other field:

```jinja
{#import "rich_text_field.jx" as RichTextField #}

<form action={{ url_for("Post.create") }} method="post">
  {{ form.title.label() }}
  {{ form.title.text_input() }}
  {{ form.title.error_tag() }}

  {{ form.body.label() }}
  <RichTextField field={form.body} />
  {{ form.body.error_tag() }}

  <button type="submit">Save</button>
</form>
```

The corresponding form field is just `JSONField` from formidable - the editor serializes its state as JSON, the form parses it back into a dict, and assigning that dict to `post.body = data` works because the model field accepts dicts (and `RichTextDocument` instances) interchangeably:

```python
import proper.forms as f


class PostForm(f.Form):
    title = f.TextField(required=True)
    body = f.JSONField(required=False)
```

### Uploads

When the user drops, pastes, or picks a file in the editor:

1. The Stimulus controller POSTs the file to `/rich_text/uploads`.
2. The controller creates an `Attachment` row with `source="rich_text"` and `pending=True`, and returns its id + url + content type.
3. The editor inserts an `attachment` node into the document with that id.
4. When the form is submitted and `Post.save()` runs, the `HasRichText` mixin sees the attachment referenced in the body and flips `pending` to `False`.

If the user closes the tab without submitting, the upload stays `pending=True` - a periodic sweep cleans it up (see [Attachment Lifecycle](#attachment-lifecycle) below).

The upload controller is generated into your app at `controllers/rich_text_controller.py` - it's your file, edit it freely:

```python
@router.resource("rich_text/uploads", pk=None)
class RichTextUploadsController(AppController):
    def create(self):
        file = self.params.get("file")
        if not file or not getattr(file, "filename", None):
            raise BadRequest("Missing file")

        attachment = Attachment(file, source="rich_text", pending=True)
        attachment.save()

        return self.render(json={
            "id": str(attachment.id),
            "url": attachment.url,
            "content_type": attachment.content_type,
        })
```

:::tip | Tightening the upload endpoint
Common adjustments to this controller: enforce a `max_size`, allowlist content types with `accept`, gate on user role, add per-user quota tracking. The controller inherits your `AppController`'s authentication policy by default; add `skip_authentication = True` if you want public uploads.
:::

### The Toolbar

The default toolbar exposes the common formatting actions: bold, italic, strike, headings (H1/H2), bullet and ordered lists, blockquote, code, links, and the file-picker upload. To change the buttons or the layout, edit `views/rich_text_field.jx` - it's a regular Jx component generated into your app.

---

## Embed Rendering

When `{{ post.body }}` renders, the AST walker emits HTML for structural nodes (paragraphs, headings, lists, marks, links) directly. For `attachment` nodes it pre-fetches every referenced `Attachment` in one query, then routes each through the Jx component `RichTextAttachment` - generated into your app at `views/rich_text_attachment.jx`:

```jinja
{#def attachment, alt=None, caption=None #}

{% if attachment.content_type.startswith("image/") %}
  {% set variant = attachment.variant(resize_to_fit=(1600, 1600)) %}
  <figure class="rich-text-image">
    <img src="{{ variant.url }}"
         alt="{{ alt or '' }}"
         loading="lazy">
    {% if caption %}<figcaption>{{ caption }}</figcaption>{% endif %}
  </figure>
{% elif attachment.content_type == "application/pdf" %}
  <a href="{{ attachment.url }}" class="rich-text-pdf" target="_blank">
    {{ attachment.filename }}
  </a>
{% else %}
  <a href="{{ attachment.url }}" class="rich-text-file" download>
    {{ attachment.filename }}
  </a>
{% endif %}
```

The framework draws the line here: it owns the AST → HTML walk for structural content, you own the visual presentation of embeds. Edit this component to add lightbox wrappers, custom captions, video thumbnails, different size limits for images, anything you want.

The default applies a `resize_to_fit: 1600x1600` variant to images. Producing a serving-sized image on demand keeps page weight down without you having to think about it; change the limit to taste, or drop the variant call to serve the original.

:::note | If you delete `RichTextAttachment.jx`
The renderer raises `ComponentNotFoundError` rather than silently dropping the embed. This is deliberate - losing embeds in production is worse than a loud error in development. Restore the file or render through a different component name in a custom renderer.
:::

---

## Rendering in Templates

In any template, interpolating the field value emits HTML:

```jinja
{{ post.body }}
```

Internally:

1. Jinja sees the `__html__()` method on `RichTextDocument` and uses it.
2. The document walks the AST, collecting attachment IDs.
3. One batched `Attachment.select().where(id.in_(ids))` resolves every embed.
4. Structural nodes render via the renderer's built-in handlers; embeds route through `<RichTextAttachment>`.
5. Result is returned as `Markup`, so Jinja knows not to escape it.

For plain text - search indices, OG meta tags, email previews, summary excerpts - call `str(...)` or use Jinja's `striptags` filter:

```jinja
<meta property="og:description" content="{{ post.body | striptags }}">
```

```python
# Or in Python:
plain = str(post.body)
```

The plain-text version renders paragraph breaks as blank lines, list items with leading `- `, headings on their own line, and embeds as `[alt text]` or `[filename]` in brackets.

The `attachments` property gives you the resolved `Attachment` rows directly, in document order:

```python
for att in post.body.attachments:
    print(att.filename, att.byte_size)
```

---

## Attachment Lifecycle

Editor uploads have a different lifecycle than form-attached files. A user drops an image into the editor, the file uploads immediately - but the form might not be submitted for another five minutes, or never. Proper handles this with two columns on `Attachment` and a periodic sweep:

- **`source`** - `"direct"` for files uploaded as part of a form submission (the historical path, via `AttachmentField`). `"rich_text"` for files uploaded by the editor.
- **`pending`** - `True` until a parent record confirms ownership. `False` once the parent's save sees the attachment referenced in a body.

The flow on a typical edit:

1. User opens the post form. Editor mounts with existing content.
2. User drops a new image. Editor uploads it → `Attachment(source="rich_text", pending=True)` created.
3. User removes a different image from the body.
4. User submits the form. `post.save()` runs.
5. `HasRichText.save` snapshots the previous body, calls `super().save()`, then:
   - Diffs old vs new attachment IDs. Removed IDs get `purge_later()`.
   - Surviving IDs get a batched `update(pending=False).where(id.in_(ids))`.

If the user never submits, the new upload stays `pending=True`. A periodic Huey task purges those past a grace period.

### The Sweep Task

The installer writes `tasks/rich_text_sweep.py` into your app:

```python
from huey import crontab

from proper.rich_text import purge_abandoned_uploads

from .main import app
from .models import Attachment


@app.queue.periodic_task(crontab(hour="3", minute="0"))
def sweep_abandoned_uploads():
    purge_abandoned_uploads(Attachment, grace_hours=24)
```

It runs daily at 3 AM and purges `source="rich_text", pending=True` rows older than 24 hours. Edit the `crontab(...)` and `grace_hours=` to suit your traffic - busier apps may want hourly sweeps, slower-typing communities may want a longer grace.

:::tip | Triggering the sweep manually
For debugging or one-off cleanup, call the helper directly: `purge_abandoned_uploads(Attachment, grace_hours=0)` purges every pending rich-text upload regardless of age.
:::

### On Delete

Deleting a post purges every attachment its body references. `HasRichText.delete_instance` collects all attachment IDs from every `RichTextField` column before calling `super().delete_instance()`, then schedules `purge_later()` for each - so a failed delete doesn't lose the files.

---

## Using a Different Editor

The framework's contract is the JSON schema, not TipTap. Any editor that produces and consumes the same shape works:

```json
{
  "type": "doc",
  "content": [
    {"type": "paragraph", "content": [
      {"type": "text", "text": "Bold ", "marks": [{"type": "bold"}]},
      {"type": "text", "text": "and italic ", "marks": [{"type": "italic"}]}
    ]},
    {"type": "attachment", "attrs": {"id": "...", "alt": "..."}}
  ]
}
```

To swap editors:

1. Replace `views/rich_text_field.jx` with one that mounts your editor.
2. Replace `assets/js/rich-text.js` with one that drives it, syncing JSON to the hidden input on update.
3. Update `config/import_map.py` to point to your editor's vendored JS.

The Python side - `RichTextField`, `RichTextDocument`, the renderer, the `HasRichText` mixin - doesn't change. The upload endpoint at `/rich_text/uploads` stays the same. Your editor's JavaScript POSTs to it and embeds the returned `attachment` node in the document.

If you don't want an editor at all (e.g. you're generating documents programmatically from imported data), drop the JS entirely and assign dicts directly:

```python
post.body = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Imported"}]},
    ],
}
post.save()
```

The field accepts dicts, the renderer renders them, the lifecycle hooks reconcile them.

---

## Testing

Rich text documents are plain dicts at the storage layer, so test setup is straightforward:

```python
def test_post_renders_body(client, db):
    post = Post.create(
        title="Hello",
        body={
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hi"}]},
            ],
        },
    )
    post = Post.get(Post.id == post.id)
    assert "<p>Hi</p>" in str(post.body.__html__())
    assert str(post.body) == "Hi"
```

For attachments, save an `Attachment` first and reference it by id in the AST:

```python
def test_post_renders_with_attachment(client, db):
    att = Attachment(_make_file(b"x", "x.png"), source="rich_text", pending=True)
    att.save()

    post = Post.create(body={
        "type": "doc",
        "content": [
            {"type": "attachment", "attrs": {"id": str(att.id)}},
        ],
    })

    refreshed = Attachment.get(Attachment.id == att.id)
    assert refreshed.pending is False  # confirmed by post.save()
```

For the upload endpoint, use `TestClient` to POST a multipart file:

```python
def test_rich_text_upload(client):
    response = client.post(
        "/rich_text/uploads",
        files={"file": ("cat.png", b"PNG-bytes", "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data and "url" in data
    assert data["content_type"] == "image/png"
```

---

## Customizing the Field

The model field is built by a factory so the backing column type can be swapped without forking the module:

```python
from playhouse.postgres_ext import JSONField as PgJSONField
from proper.rich_text import make_rich_text_field


# Postgres-native jsonb column - supports indexes, jsonpath, etc.
RichTextField = make_rich_text_field(PgJSONField)


class Post(HasRichText, BaseModel):
    body = RichTextField(attachment_cls=Attachment)
```

The default parent is Proper's `JSONField` (a `TextField` that serializes JSON manually), which works on every database Peewee supports. Swap when you need the underlying engine's native JSON features.

---

## Related

- [File Storage](/docs/storage) - the `Attachment` model and storage services rich text builds on.
- [Working with Forms](/docs/forms) - `JSONField` and form rendering.
