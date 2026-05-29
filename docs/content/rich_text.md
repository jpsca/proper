---
title: Rich Text
description: |
  How to store, render, and edit rich text content in Proper, including embedded image and file attachments.
number_headers: true
---

# Rich Text

This guide covers Proper's rich text addon - a field type that stores
formatted documents with embedded attachments, plus a default editor
that knows how to produce and edit them.

After reading this guide, you will know:

- What rich text means in Proper, and how to install and configure it.
- How to create, render, style, and customize rich text content.
- How the bundled editor handles attachments.

The companion [File Storage](/docs/storage) guide covers attachments at the level rich text builds on. Read it first if you haven't met the `Attachment` model.

---

## Introduction

Proper's rich text addon facilitates the handling and display of text that includes formatting elements beyond plain text such as bold, italics, colors, hyperlinks, and tables.

It integrates a modern rich text editor called [Lexxy](https://basecamp.github.io/lexxy/) with tons of out-of-the-box features including file uploads and embedding images. The editor can also be easily extended to add things like @mentions, emojis, or whatever advanced text feature your app might need.

:::figure | The default rich text editor
![Lexxy](/assets/images/rich_text/lexxy.png)
:::

---

## Setup

To install the rich text addon, run:

```bash
$ proper install rich_text
```

It does the following:

- Installs the _storage_ addon, if it's not already, you need it for attachments.
- Adds the js and css files for the Lexxy editor
- Creates the components for the editor and for rendering attachments.
- Adds a task for cleaning up abandoned uploads.

Now run the migrations to create the `attachment` table added by the _storage_ addon.

```bash
$ proper db migrate
```

---

## Creating Rich Text content

The rich text addon works with existing text fields so you don't need to create a database migration to add it to your models.

You do need, however, to update the _python_ classes involved.

### Models

Let's say you have a model like this:

```python {title="models/post.py" hl_lines="7"}
import peewee as pw

from .base import BaseModel

class Post(BaseModel):
    title = pw.CharField()
    body = pw.TextField(null=True)
```

and you want to make the body rich-text. To do so, update the field type and add the `HasRichText` mixin:

```python {title="models/post.py" hl_lines="2 4 7 9"}
import peewee as pw
from proper.rich_text import HasRichText, RichTextField

from .attachment import Attachment
from .base import BaseModel

class Post(BaseModel, HasRichText):
    title = pw.CharField()
    body = RichTextField(Attachment, null=True)
```

As you see, you also need to pass your `Attachment` model to it, so it knows where to upload files.

**If you don't want to use image/file uploads in that field**, pass `None` instead and drop the mixin. The result is much simpler:

```python {title="models/post.py" hl_lines="2 8"}
import peewee as pw
from proper.rich_text import RichTextField

from .base import BaseModel

class Post(BaseModel):
    title = pw.CharField()
    body = RichTextField(None, null=True)
```

### Forms

Change your `f.TextField` into a `f.RichTextField`:

```python {title="forms/post.py" hl_lines="10"}
from proper import forms as f

from myapp.models import Post

class PostForm(f.Form):
    class Meta:
        orm_cls = Post

    title = f.TextField()
    body = f.RichTextField(required=False)
```

`f.RichTextField` is a thin subclass of `f.TextField` that knows how to coerce a `RichTextDocument` (the runtime value of a `RichTextField` model column) into the HTML string the form needs to render and submit.

### Views

Finally you need to render the editor. The addon created a component for it, you just have to import it and use it:

```python {title="views/post/form.jx" hl_lines="2 14"}
{#import "form.jx" as Form #}
{#import "rich_text_editor.jx" as RichTextEditor #}
{#js "js/nestedform.js" #}
{#def form, action='', method='post' #}

<Form method={{ method }} action={{ action }}>
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
  {{ content }}
</Form>

```

The editor has many ways to customize it - adding or removing features, editing the toolbar buttons, etc. - you will read about it in the [Customizing the Editor](#customizing_the_editor) section.

---

## Rendering Rich Text content

Instances of `rich_text.RichTextField` can be directly embedded into a page because they have already sanitized their content for a safe render. You can display the content as follows:

```html+jinja
{{ post.body }}
```

`RichTextDocument.__html__` safely transforms the data into an HTML String, including attachments. On the other hand `RichTextDocument.__str__` returns a plain text string without HTML tags, useful for using it in metadata.

You probably also want to include the `lexxy-content.css`
stylesheet to give your content the same styles it has in the editor:

```html+jinja
{#css css/lexxy-content.css #}

{{ post.body }}
```

### Rendering embedded images and attachments

The HTML code stored in the database by a `rich_text.RichTextField` uses special `<proper-attachment>` tags to reference attachments (instead of `<img>` tags).

On rendering, the UUIDs of the attachments are collected, loaded in a single query, and rendered to HTML using the **`views/rich_text_attachment.jx`** component, added to your application by the addon. 

You can customize how to render attachments editing that file. It receives:

- `attachment` - the resolved `Attachment` row.
- `alt`, `caption` - the text the user typed for this embed in the editor.
- Any other attribute the editor wrote on the placeholder tag.

For example, here is a version that renders videos using a `<video>` tag, resizes images to 800 pixels, and falls back to a plain download link for everything else:

```html+jinja {title="views/rich_text_attachment.jx"}
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

See the [File Storage](/docs/storage) guide for details on `variant()`, previewable content types, and how to add support for new ones.

---

## Customizing the Editor
{#customizing_the_editor}

Depending on where you are using the editor, you might want to disable some features, enable others, or update the presentation of the editor. This section guides you on how to do that.

### Customizing the editor features

At minimum, you render the editor component like this:

```html+jinja
{#import "rich_text_editor.jx" as RichTextEditor #}

<RichTextEditor field={{ form.myfield }}></RichTextEditor>
```

The `rich_text_editor.jx` component supports the following options out of the box:

Option           | Description
---------------- | --------------------------
`toolbar`        | Pass `"false"` (as a string) to disable the toolbar entirely. By default, the toolbar is rendered using the `rich_text_toolbar.jx` component.
`toolbar-upload` | Control which upload button(s) appear in the toolbar. Accepts `"file"`, `"image"`, or `"both"` (default). The image button restricts the file picker to images and videos (`accept="image/*,video/*"`), which triggers the native photo/video picker on iOS and Android. The file button opens an unrestricted file picker.
`attachments`    | Pass `"false"` (as a string) to disable attachments completely. By default, attachments are supported, including paste and drag & drop support. For finer-grained control - keeping attachments enabled while restricting which content types are accepted - use `permitted-attachment-types`.
`markdown`       | Pass `"true"` (as a string) to enable Markdown support.
`multi-line`     | Pass `"false"` (as a string) to force single line editing.
`permitted-attachment-types` | Restrict the editor to a specific allowlist of attachment content types. Unset (the default) permits any content type. Example: `<RichTextEditor permitted-attachment-types="application/epub+zip application/pdf" field={{form.body}} />`.

The editor also supports standard HTML attributes: `placeholder`, `class`, `disabled`, `autofocus` etc.


### Customizing the toolbar

The toolbar is rendered using the `views/rich_text_toolbar.jx` component, added by the addon to your application.

In there you can update classes, replace the button icons, and add or remove buttons.

Beware that removing a button _doesn't mean removing the ability to use the format_. Files/images can be uploaded by drag-and-drop (use the `attachments` option to disable them), and many formats have standard keyboard shortcuts that will still work: `ctrl+b` for bold, `ctrl+i` for italics, `ctrl+k` for adding links, etc.

---

## Extending the editor

"Prompts" is the Lexxy mechanism that lets you implement features like `@mentions`, `/commands`, or any other trigger-based suggestions. When you select an item from the prompt, you have two options:

A. Insert the item as a custom attachment. This allows you to use a standard component to customize how it renders and to use code to process it on the server side.
B. Insert the item as free text in the editor.

Lexxy also lets you configure how to load the items: inline or remotely, and how to do the filtering (locally or on the server).

### Free HTML attachments

This is the simplest type of prompt, that simply inserts the prompt item HTML directly in the editor. This is useful for things like hashtags, emojis, or other inline elements that don't require server-side processing.

To enable these, you must add the `insert-editable-text` attribute to the `<lexxy-prompt>` element:

```html
<RichTextEditor field={{post.body}}>

  <lexxy-prompt trigger=":" insert-editable-text>
    <lexxy-prompt-item search="joy laughing face">
      <template type="menu">😂 :joy</template>
      <template type="editor">😂</template>
    </lexxy-prompt-item>
    <lexxy-prompt-item search="heart red heart">
      <template type="menu">❤️ :heart</template>
      <template type="editor">❤️</template>
    </lexxy-prompt-item>
    <lexxy-prompt-item search="+1 thumbs up like">
      <template type="menu">👍 :+1</template>
      <template type="editor">👍</template>
    </lexxy-prompt-item>
    <lexxy-prompt-item search="tada party popper celebration">
      <template type="menu">🎉 :tada</template>
      <template type="editor">🎉</template>
    </lexxy-prompt-item>
  </lexxy-prompt>

</RichTextEditor>
```

Typing the `trigger` is what makes the menu appear.

:::figure | Just like that, an emoji picker
![Emoji picker](/assets/images/rich_text/emojis.png)
:::

When configured like this, if you select an item from the prompt, the content of the `<template type="editor">` will be inserted directly in the editor as HTML you can edit freely (as long as the HTML is compatible with the tags that Lexxy supports).


---

## Attachments

An "attachment" inside a rich text document is any file the user drops into the editor: an image they paste, a PDF they upload, a video clip, a spreadsheet. The bytes live wherever your storage service is configured to put them; the document just holds a small placeholder tag pointing at the `Attachment` row.

The placeholder looks like this in the stored HTML:

```html
<proper-attachment sgid="0193c9f7-...-2dba"
  caption="A picture of my cat"></proper-attachment>
```

This section walks through how those rows get created, when they get confirmed or cleaned up, and how to work with them from your Python code.


### The attachment lifecycle

Unlike a regular form field, the editor uploads files _before_ the user submits the form. The flow looks like this:

1. The user drops a file into the editor (or clicks the upload button).
2. The browser POSTs the file's metadata to your app's `DirectUpload.create` endpoint. An `Attachment` row is created with `source="direct"` and `pending=True`, and the server returns a signed URL.
3. The browser PUTs the file bytes directly to storage using that URL.
4. The editor inserts a `<proper-attachment sgid="...">` placeholder in the document.
5. When the user submits the form, the parent model's `save()` reconciles the body with what was there before.

The `pending` flag is the key: until step 5 happens, the row is provisional. The user might close the tab, hit "back", or just walk away. The sweeper job described below cleans up rows that stay pending too long.


### Save and delete behavior

The `HasRichText` mixin (which you added to your model in the [Models](#models) section) hooks into two events:

**On save**, the mixin:

- Marks every attachment still referenced in the new body as `pending=False`. The upload now has a home and the sweeper will leave it alone.
- Schedules a purge for every attachment that _was_ in the previous body but is no longer in the new one. Editing a post to remove an image frees its storage automatically.

**On delete**, the mixin schedules every attachment referenced by every rich text column on the record for purge. Tearing down a post tears down its embedded files too.

Purges are dispatched as background jobs, so they don't block the save or the user's request. If your record has multiple `RichTextField` columns, the mixin handles them all - no extra configuration needed.

If you build a model that holds rich text but for some reason should _not_ own its attachments (e.g. attachments shared between records), don't include `HasRichText`. The document will still render fine; you just lose the automatic cleanup.


### Sweeping abandoned uploads

Pre-uploaded files that never get confirmed are orphans. They take up storage with no document pointing at them. The rich-text addon generates a periodic task that sweeps these up:

```python {title="tasks/abandoned_uploads_sweep.tt.py"}
from huey import crontab
from proper.rich_text import purge_abandoned_uploads

from myapp.main import app
from myapp.models import Attachment


@app.queue.periodic_task(crontab(hour="3", minute="0"))
def sweep_abandoned_uploads():
    purge_abandoned_uploads(Attachment, grace_hours=24)
```

By default it runs at 3 AM each day and purges any `pending=True` row older than 24 hours. Tune the crontab and `grace_hours` to taste:

- A short grace period reclaims storage faster but risks deleting an upload while the user is still composing a long post.
- A long grace period is gentler on users but keeps orphans around longer.

The sweep only touches rows where `source="direct"`, so other addons that pre-upload with their own lifecycle policy aren't affected.


### Accessing attachments from Python

A `RichTextDocument` (the runtime value of a `RichTextField` column) exposes the attachments it references:

```python
post = Post.get(slug="my-post")

# All attachments in document order, deduplicated, fetched in one query.
for att in post.body.attachments:
    print(att.filename, att.content_type, att.byte_size)
```

The list is loaded lazily on first access and cached for the lifetime of the document instance, so reading `post.body.attachments` more than once does not hit the database again.

This is useful for things like building a gallery of every image in a post, picking a thumbnail for an OpenGraph tag, or feeding attachment metadata into an external search index.

---

## Related

- [File Storage](/docs/storage) - the `Attachment` model and storage services rich text builds on.
- [Working with Forms](/docs/forms) - `JSONField` and form rendering.
