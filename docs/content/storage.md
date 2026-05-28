---
title: File Storage
description: |
  An overview of how to upload, store, and serve user files in Proper. Covers configuring storage services, attaching files to records, generating image variants, validating uploads, and serving files in production.
number_headers: true
---

# File Storage

This guide covers how to attach files to your peewee models and how Proper stores, validates, and serves them.

After reading this guide, you will know:

- How to install the storage addon and configure one or more services.
- How to attach a single file or many files to a record.
- How to link to and serve attachments in development and in production.
- How to validate uploaded files by size and content type.
- How to transform images and generate variants on demand.
- How to preview non-image files like PDFs and videos.
- How to implement support for additional storage services.

The companion [`AttachmentField` section](/docs/forms#attachmentfield) in the Forms guide covers the field that handles uploads inside a form in depth. Use this guide as the  reference for storage but jump there for form mechanics.

---

## What is File Storage?

File Storage in Proper handles uploading files to a cloud service, like Amazon S3, or to your local disk for testing and development. It provides a single `Attachment` model so the rest of your application can treat any uploaded file the same way regardless of where its bytes live.

The subsystem has two cooperating pieces:

- **Storage services.** A *service* knows how to put bytes somewhere and get them back: `Disk` writes to a folder on the local filesystem, `S3` talks to Amazon S3 (and any service that speaks the S3 protocol). Each service is named in your config, and one service is active per environment.
- **The `Attachment` model.** Every uploaded file gets a row in the `attachment` table that records its filename, content type, byte size, which service holds the bytes, and a few other flags. Your own peewee models reference attachments through a regular `ForeignKeyField`.

Because the application code talks to `Attachment` and never to a service directly, swapping `Disk` for `S3` between development and production is one config change. A user's avatar is stored in `storage/` on a developer's laptop, in `temp/storage/` during the test run, and in an S3 bucket in production. None of that ripples into model or controller code.

### Requirements

Some features of File Storage depend on third-party software which Proper will not install, and must be installed separately:

- [libvips v8.6+](https://www.libvips.org/install.html) for making thumbnails and image transformations. You will also need the `pyvips` python package.
- [ffmpeg v3.4+](https://ffmpeg.org/) for video previews.
- [poppler](https://poppler.freedesktop.org/) for PDF previews.

:::note | libvips
On macOS install the system library with `brew install vips`; on Debian or Ubuntu, `apt install libvips-dev`. For other systems, see the [libvips installation page](https://www.libvips.org/install.html){target=_blank}.

Then add `pyvips` to your project:

```bash
uv add pyvips
```
:::

---

## Setup

The storage addon is installed on demand; a freshly generated application doesn't carry it by default. From the project root:

```bash
$ proper install storage
$ proper db migrate
```

This writes a few files into your application:

- An `Attachment` model that lives in your application and inherits its powers from the one in Proper, so you can extend it with extra fields or methods. It uses an UUID as primary key.
- Drop-in Jx components for file inputs with image previews, paired with Stimulus controllers and CSS.
- Several controllers at `storage_controller.py`:

Controller                  | Purpose
--------------------------- | --------------------
`StorageRedirectController` | Redirect to the storage service's native URL (e.g. a presigned S3 link) for signed URLs. Fallback to streaming if the service doesn't implement them.
`StorageProxyController`    | Streams the attachment bytes through the app.
`DirectUploadController`    | To upload files directly to remote services plus a fallback for the Disk service.


### Services Configuration

Storage services are declared in `config/storage.py` as a dictionary. Each entry has a name (chosen by you) and a `type` plus any options the service needs:

```python
# config/storage.py
import os

STORAGE_SERVICES = {
    "local": {
        "type": "Disk",
        "root": "storage/",
    },
    "test": {
        "type": "Disk",
        "root": "temp/storage",
    },
    "amazon": {
        "type": "S3",
        "bucket": "my-app-uploads",
        "region": "us-east-1",
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    },
}

STORAGE = "local"
if env == "prod":
    STORAGE = "amazon"
elif env == "test":
    STORAGE = "test"
```

`STORAGE` names the default service. Application code never references a service name directly; it picks up the active one whenever you create an `Attachment`.

You can declare more services than you actively use. The lookup is lazy: a service is instantiated only the first time someone or something writes to it.

### Disk Service

The Disk service writes files under a single root folder. Configuration takes one option, `root`, interpreted relative to the project root (one level above `app.root_path`):

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

If it doesn't already exists, the folder is created the first time the service is used.

:::tip
`storage/` is in your `.gitignore` (the new-app generator already does it). Uploaded files are user data, not source, and they don't belong in version control.
:::

### S3 Service

The S3 service uploads to Amazon S3 or any service that speaks the S3 protocol (DigitalOcean Spaces, Cloudflare R2, MinIO, Wasabi, Backblaze B2, ...).

Required: `bucket`. Everything else is optional.

```python
"amazon": {
    "type": "S3",
    "bucket": "my-app-uploads",
    "region": "us-east-1",
    "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
}
```

If you omit the credentials, `boto3` falls back to its default credential chain (environment variables, IAM instance profile, shared AWS config files). On a properly-configured EC2 instance or container, you don't need to put credentials in your config at all.

For non-AWS services, set `endpoint`:

```python
"spaces": {
    "type": "S3",
    "bucket": "my-bucket",
    "region": "nyc3",
    "endpoint": "https://nyc3.digitaloceanspaces.com",
    "access_key_id": os.getenv("DO_SPACES_KEY"),
    "secret_access_key": os.getenv("DO_SPACES_SECRET"),
}
```

The same shape covers Cloudflare R2, MinIO, Wasabi, and similar; check the provider's docs for the right `endpoint` value.

:::note
The S3 service requires `boto3`. Add it to your dependencies:

```bash
$ uv add boto3
```
:::

### Public Access

Public access is decided at the *service* level. Each entry in `STORAGE_SERVICES` can carry a `public: True` flag; every attachment stored in that service is reachable through a stable, unsigned URL. Attachments in services without the flag (the default) are reachable only through a signed URL with an expiration.

```python
STORAGE_SERVICES = {
    "local": {
        "type": "Disk",
        "root": "storage/",
    },

    # A second service for files that are genuinely world-readable:
    "public": {
        "type": "Disk",
        "root": "storage/public",
        "public": True,
    },

    "amazon": {
        "type": "S3",
        "bucket": "private-uploads",
    },

    "amazon_public": {
        "type": "S3",
        "bucket": "public-assets",
        "public": True,
    },
}
```

The benefit of routing public files through their own service is operational clarity: the bucket policies, CDN configuration, and access logs all align with the access mode. There's no risk of accidentally flipping a single attachment's `public` flag and exposing data, because the access mode is a property of *where* the bytes live.

To put a new attachment in a public service, pass `service_name=` either when constructing it manually or when declaring the form field:

```python
# Manually:
att = Attachment(upload, service_name="public")
att.save()

# Through the form field:
avatar = f.AttachmentField(Attachment, service_name="public")
```

### Baseline Configuration

Three more keys, all populated by the installer, control how files are served and how variants are encoded:

```python
STORAGE_ALLOWED_INLINE = [
    "image/*",
    "video/*",
    "application/pdf",
]

STORAGE_ALLOWED_VARIANTS = [
    "image/png",
    "image/jpeg",
    "image/gif",
]

STORAGE_FALLBACK_FORMAT = "png"
```

`STORAGE_ALLOWED_INLINE` is a list of glob patterns (matched with `fnmatch`) for content types that should be served inline in the browser. `<img>` shows the image, `<video>` plays the video, the PDF opens in the browser viewer. Anything not matched is served with `Content-Disposition: attachment`, triggering a download dialog.

`STORAGE_ALLOWED_VARIANTS` is a list of glob patterns for source content types whose format should be **preserved** when generating a variant. A source PNG produces a PNG variant; a source JPEG produces a JPEG variant. Add `image/webp` or `image/avif` if your application produces those.

`STORAGE_FALLBACK_FORMAT` is the format used for variants whose source content type is *not* in `STORAGE_ALLOWED_VARIANTS`. The default is `"png"` (lossless, supports transparency). Set it to `"jpg"` or `"webp"` if smaller files matter more than fidelity. A caller-supplied `save={"format": "..."}` always overrides both rules - see [Format Conversion](#format-conversion).

---

## Attaching Files to Records

The recommended way to attach a file is to give your model a `ForeignKeyField` that points at `Attachment`. There is no magic `attached_as` declaration: a regular foreign key shows up in migrations, plays well with normal queries, and lets two records share the same blob if you ever need to copy a record.

### Single Attachment

For "one file per record" relationships - e.g. an avatar on a user, a cover on a book, a logo on an organization - declare a nullable foreign key:

```python {hl_lines="9"}
# models/user.py
import peewee as pw
from .attachment import Attachment
from .base import BaseModel

class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)
    avatar = pw.ForeignKeyField(Attachment, null=True)
```

That's the entire wire-up. `user.photo` is either `None` or an `Attachment` instance. Reading attributes works as you'd expect:

```python
user.photo.url
user.photo.filename
user.photo.byte_size
user.photo.content_type
```

To assign an attachment, you build it and save it before pointing the FK at it:

```python {hl_lines="1-2"}
att = Attachment(upload, filename="avatar.jpg")
att.save()
user.photo = att
user.save()
```

The order matters because the `Attachment.id` column has no `default=uuid4`. The id is generated when you call `save()`, not when you call `Attachment(...)`. That's intentional: it makes `attachment.id is None` truthfully signal "not in the database yet" so you can't accidentally set a foreign key to a UUID that points at no row.

If you want to skip the ordering dance, use `AttachmentField` on a form ([Forms and Attachments](#forms-and-attachments)) - the field handles the build, save, and assign in one `form.save()` call.

### Multiple Attachments

For "many files per record" - e.g. photos in a gallery, documents on a project, supporting evidence on a claim - use a normal through-model:

```python
class Photo(BaseModel):
    gallery = pw.ForeignKeyField(Gallery, backref="photos")
    attachment = pw.ForeignKeyField(Attachment)
    caption = pw.CharField(default="")
    position = pw.IntegerField(default=0)


class Gallery(BaseModel):
    name = pw.CharField()
    # gallery.photos is provided by the backref above
```

`gallery.photos` is now an iterable of `Photo` rows, each carrying its own `attachment`, `caption`, and `position`. The through-model is also the natural place for any per-attachment data: ordering, alt text, captions, who uploaded it, when, in what context.

If you don't need any extra columns, you can still use a through-model with just two foreign keys. It's a tiny amount of boilerplate that pays off the first time you want to add ordering or labels.

### Attaching File or IO Objects

The `Attachment` constructor accepts anything with a `read()` method, like an open file, an in-memory `BytesIO`, or a request body. It also accepts the `MultipartPart` objects produced by the form parser, which is what `AttachmentField` uses under the hood.

```python
from io import BytesIO
from .attachment import Attachment

# From in-memory bytes:
data = generate_report_pdf(...)
att = Attachment(
    BytesIO(data),
    filename="report.pdf",
    content_type="application/pdf",
)
att.save()

# From an open file:
with open("/tmp/photo.jpg", "rb") as fp:
    att = Attachment(fp, filename="photo.jpg")
    att.save()

# From a remote URL via httpx:
import httpx
resp = httpx.get("https://example.com/avatar.png")
att = Attachment(BytesIO(resp.content), filename="avatar.png")
att.save()
```

Things to know about the constructor:

- `service_name` defaults to whatever `STORAGE` resolves to at runtime. Pass `service_name="amazon"` to override (write to a different bucket, for example, even though the active default is `local`).
- `filename` is parameterized: lowercased, special characters replaced with dashes, the extension preserved as a separate part. `"My Photo!.JPG"` becomes `"my-photo.jpg"` on disk.
- `content_type` is detected from the filename extension when you don't supply it. The fallback is `application/octet-stream`.
- `byte_size` is populated by the service during `save()` - never pre-fill it.
- `id` is `None` until `save()` runs.

### Forms and Attachments

The form-side mechanics are covered in detail in the [`AttachmentField` section](/docs/forms#attachmentfield) of the Forms guide. The orientation goes here.

For any `ForeignKeyField(Attachment)` column on a model, the corresponding form field is `f.AttachmentField`:

```python
# models/forms/user_form.py
from proper import forms as f
from ..attachment import Attachment
from ..user import User


class UserForm(f.Form):
    name = f.TextField()
    email = f.EmailField()
    avatar = f.AttachmentField(Attachment, required=False)

    class Meta:
        orm_cls = User
```

The controller doesn't need to know an upload is involved:

```python
def update(self):
    self.form.save()
    self.response.redirect_to("User.show", self.user)
```

`form.save()` reads the multipart submission, builds an `Attachment(upload)`, calls `.save()` on it (uploading the bytes to the active service), assigns the new attachment to `user.photo`, and queues the previous attachment for deletion. All in one call.

The field interprets a structured payload composed of two sub-inputs:

User action          | `<field>[file]` | `<field>[_destroy]` | What `save()` does
-------------------- | --------------- | ------------------- | -------------------------------------------------
Uploaded a new file  | populated       | (any)               | Save new attachment, queue old one for deletion.
Clicked "Remove"     | empty           | `"1"`               | Clear the FK, queue old one for deletion.
Left the field alone | empty           | `"0"` or absent     | Preserve the existing attachment unchanged.

The render helpers `file_input()` and `destroy_input()` produce the two HTML inputs, and the `image_input.jx` component the storage addon ships does the JS work for drag-and-drop, preview, and the "Remove" toggle. See [Rendering Forms - Attachment uploads](/docs/form_rendering#attachment-uploads) for the HTML side.

For uploads that don't fit the foreign-key pattern - a one-off CSV import, a webhook from an outside service, a parser that reads bytes and discards the file - work directly with `Attachment` ([Attaching File or IO Objects](#attaching-file-or-io-objects)).

### Validating Attached Files

`AttachmentField` ships with two server-side validators - `max_size` and `accept` - and accepts custom validation through the standard form `validate_<field>` hook. They run during `form.validate()`, before any upload would otherwise be saved.

**Limiting file size.** Pass `max_size` in bytes:

```python
class BookForm(f.Form):
    title = f.TextField()
    cover = f.AttachmentField(
        Attachment,
        max_size=5 * 1024 * 1024,  # 5 MB
    )
```

A failed check produces `errors.FILE_TOO_LARGE` with a formatted size in the error args. The default message is *"File size should be 5 MB or less"*.

`max_size` is a form-level check: the multipart parser still has to receive the bytes before the field can measure them. For a hard ceiling that rejects oversized requests *before* they're parsed, set the framework-wide `MAX_CONTENT_LENGTH` in `config/main.py`. The two work together: the framework limit protects the server from huge uploads, `max_size` produces friendly per-field errors for files that fit the request limit but exceed your application's policy.

**Restricting content types.** Pass `accept` as a list of patterns:

```python
class UserForm(f.Form):
    avatar = f.AttachmentField(
        Attachment,
        accept=["image/*"],
    )
```

`accept` uses `fnmatch` semantics, so `image/*` covers `image/jpeg`, `image/png`, `image/webp`, and so on. List specific types when you want to be stricter:

```python
attachment = f.AttachmentField(
    Attachment,
    accept=["image/png", "image/jpeg", "image/webp"],
)
```

A failed check produces `errors.INVALID_CONTENT_TYPE` with the rejected list in the error args. Comparison is case-insensitive on both sides.

The HTML `accept` attribute on the file input is a separate thing - it filters the picker dialog client-side but doesn't validate. Always pair `accept=` on the field with the same `accept=` on the rendered input; the addon's `image_input.jx` component does this for you.

**Skipping validation on bound attachments.** Both `max_size` and `accept` are skipped when the form value is an existing `Attachment` row rather than a fresh upload. The check looks at whether the value has a `size` (or `content_type`) attribute; if not, the validator passes.

This matters when you re-render an edit form. The user opens the page, the form binds the existing avatar, the user changes their name (not the avatar), and submits. The form value at that point is the bound `Attachment` row, not an upload, so the size and content-type rules don't apply. Existing attachments are grandfathered until the user actually replaces them, at which point the new upload is checked against the current rules.

**Custom validators.** For checks beyond size and content type, use the standard form `validate_<field>` hook:

```python
class DocumentForm(f.Form):
    file = f.AttachmentField(Attachment, accept=["application/pdf"])

    def validate_file(self):
        upload = self.file.value
        if upload is None or isinstance(upload, Attachment):
            return  # nothing new to check

        filename = getattr(upload, "filename", "") or ""
        if " " in filename:
            self.file.error = "Filename must not contain spaces"
```

The `isinstance(upload, Attachment)` guard mirrors the built-in skip - don't re-validate an already-saved attachment. For reusable rules, write your own subclass of `AttachmentField`.

**Customizing error messages.** Pass `messages={...}` with the message key and your replacement template:

```python
cover = f.AttachmentField(
    Attachment,
    max_size=2 * 1024 * 1024,
    accept=["image/jpeg", "image/png"],
    messages={
        "file_too_large": "Cover image must be 2 MB or less",
        "invalid_content_type": "Cover image must be a JPEG or PNG",
        "required": "Please choose a cover image",
    },
)
```

For application-wide message changes, define a translation in your locale files instead of repeating `messages={...}` on every field. See the [Internationalization guide](/docs/i18n) for the keys and overrides.

---

## Removing Files

To remove an attachment, call one of the purge methods. Both delete the file from the active service and remove the database row; they differ in *when* the work happens.

```python
# Synchronously destroy the avatar and actual resource files.
user.photo.purge()

# Enqueues a Huey task, returns immediately
user.photo.purge_later()
```

`purge()` calls `service.purge()`, removes any variants of the attachment, and deletes the row. It's the right call from a CLI script or a background job, where you want the work done before the next thing runs.

`purge_later()` enqueues a Huey task that does the same work in a worker process. The task takes only the attachment's primary key and re-fetches the row before acting, so it's safe even if the row is deleted some other way before the task runs.

`AttachmentField` uses `purge_later()` for the previous attachment after a successful replacement: the new file is uploaded and saved synchronously (you want to know if that fails), but the cleanup of the old file happens in the background (a slow S3 delete shouldn't block the form response).

To remove just the variants of an attachment, leaving the original alone:

```python
user.photo.purge_variants()        # synchronous
user.photo.purge_variants_later()  # background
```

This is occasionally useful after a design change that invalidates dimensions, or in a migration that switches output format.

---

## Serving Files

File Storage in Proper supports two ways to serve files: redirecting and proxying.

:::warning | Public by default
Both storage controllers are publicly accessible by default. The generated URLs are practically impossible to guess, but permanent by design. If your files require a higher level of protection consider implementing [Authenticated Controllers](#authenticated_controllers).
:::

### Redirect Mode

The permanent url of your attachment is `attachment.url`. The property returns a URL containing a token signed with your application's secret key.

```python
user.photo.url  # or user.photo.get_redirect_url()
# /storage/redirect/eyJpZCI6IC1mM...droorU1KWTkQ/my-avatar.jpg
```

This is the same as doing:

```python
app.url_for(
    "StorageRedirect.show",
    token=user.photo.generate_token(salt="redirect"),
    filename=user.photo.filename,
)
```

The `StorageRedirectController` decodes the token, checks the signature, looks up the attachment, and redirects to the actual service endpoint. This indirection decouples the service URL from the actual one.

The URL of the service might be valid only for a few minutes (15 is the Amazon S3 default), but the one returned by `user.photo.url` never changes.

:::note
Technically the URL _does_ change, but only if you remove your current secret key, because the token generated will become invalid. So, if you do that, you need to also purge the cache of any page with old URLs.
:::

###  Proxy Mode

Optionally, files can be proxied instead. This means that your application servers will download file data from the storage service in response to requests. This can be useful for serving files from a CDN.

```python
user.photo.get_proxy_url()
# /storage/proxy/sdaRCI6IC1mM...mieauU1KWXD/my-avatar.jpg
```

The proxy and redirect URLs look very similar, but the tokens are not interchangeable, simply changing "redirect" to "proxy" in the URL will not work


### Authenticated Controllers
{#authenticated_controllers}

The signed token proves that a URL was generated by your code; it doesn't prove that the *current viewer* should be allowed to see the file.

To gate access on application-level rules (e.g. team membership, ownership, payment status, etc.) edit `StorageRedirectController`

1. Remove the `skip_authentication = True` rule that makes the controller public;
2. Put the checks inside

```python {hl_line="2,11"}
class StorageRedirectController(AppController):
    # skip_authentication = True

    @router.get("storage/redirect/:token/:filename")
    def show(self):
        attachment = Attachment.get_signed(
            self.params.get("token"),
            salt="redirect",
            max_age=None,
        )
        if not attachment:
            raise NotFound

        # extra checks here
        # ...
```

This will gate-keep **all** uploaded files. If you want something more granular, create a new controller instead:

```python {hl_lines="5"}
class DownloadController(AppController):
    def show(self):
        att = Attachment.get_signed(
            self.params["token"],
            salt="secret",
            max_age=None,
        )
        if not att:
            raise NotFound

        service_url = attachment.service_url()
        if service_url:
            self.response.redirect_to(service_url)
        else:
            attachment.send_file()
```

And create the URLs for it like this:

```python
# "secret_file" is an attachment field
document.secret_file.url_for("Download.show". salt="secret")
```

Choose a different salt than "redirect", otherwise the generated token will be usable to get the file through the `StorageRedirectController`.


### Displaying Images, Videos, and PDFs

`attachment.url` works wherever a string URL goes. The most common shapes:

```html+jinja
{# An image #}
<img src="{{ user.photo.url }}" alt="{{ user.name }}">

{# A video, served inline #}
<video src="{{ post.clip.url }}" controls></video>

{# A link that downloads with the original filename #}
<a href="{{ document.file.url }}" download>{{ document.file.filename }}</a>

{# A list of photos with thumbnails (variants are covered later) #}
{% for photo in gallery.photos %}
  <a href="{{ photo.attachment.url }}">
    <img src="{{ photo.attachment.variant(resize_to_fill=(200, 200)).url }}">
  </a>
{% endfor %}
```

Whether the file shows inline (the `<img>` actually renders) or downloads (the browser opens a Save dialog) is decided by `STORAGE_ALLOWED_INLINE` ([Baseline Configuration](#baseline-configuration)). The default covers `image/*`, `video/*`, and `application/pdf` - exactly the formats that browsers know how to display in place. For everything else, the browser saves the file.

In a JSON response, treat the URL like any other field:

```python
def show(self):
    self.response.json = {
        "id": self.user.id,
        "name": self.user.name,
        "avatar_url": self.user.photo.url if self.user.photo else None,
    }
```

For PDFs, modern browsers render them in an embedded viewer when served inline. `STORAGE_ALLOWED_INLINE` defaults include `application/pdf`, so a `<iframe src="{{ doc.file.url }}">` works without extra configuration. If you want PDFs to download instead, drop `application/pdf` from `STORAGE_ALLOWED_INLINE`.

When you need a full URLs (meaning one that include the domain name) - for OpenGraph, emails, etc. - you can use:

```python
user.photo.get_redirect_url(_full=True)
# or
user.photo.get_proxy_url(_full=True)
```

---

## Downloading Files

Sometimes you need to read an attachment's bytes back into Python: parsing a CSV, hashing a file for a deduplication check, re-uploading to a different service, transcoding through an external tool. `download()` returns the file as `bytes`:

```python
data = user.photo.download()
# => b'...'
```

Use it for parsing, hashing, transcoding, or any work that needs the file in memory. The whole file is materialized at once, which is fine for images and small documents but inappropriate for multi-gigabyte uploads. For very large files, write a streaming controller that reads from the underlying service and pipes to the response.

Reading the bytes through `download()` always goes through the service: on `Disk`, that's a `path.read_bytes()`; on `S3`, a `get_object` followed by reading the body.

---

## Analyzing Files

Proper does **not** automatically extracts metadata (image dimensions, audio bitrate, video duration) from uploaded files out of the box. The reason is mostly pragmatic: the analysis pipeline depends on a small zoo of native libraries (libvips for images, ffprobe for video, mutagen for audio) and we'd rather you opt into the ones you actually need.

Every `Attachment` carries a `metadata` JSON column that you can populate yourself:

```python
from PIL import Image

att = Attachment(upload, filename="photo.jpg")
att.save()

# Compute and store dimensions:
img = Image.open(att.download_to_tempfile())
att.metadata = {
    "width": img.width,
    "height": img.height,
    "alt": "Sunset over the harbor",
    "captured_at": img.getexif().get(36867),
}
att.save()
```

(`download_to_tempfile()` is not a built-in method - this example sketches the shape of analyzer code you'd write yourself; pyvips, Pillow, ffprobe, and mutagen all accept either bytes or paths and the bytes are one `download()` away.)

For analysis that should always run, override `save()` on your `Attachment` subclass:

```python
class Attachment(app.attachment_for(BaseModel)):
    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        if (
            self._upload is None
            and self.content_type.startswith("image/")
            and not self.metadata
        ):
            # Newly persisted image, no metadata yet - extract dimensions.
            try:
                w, h = self._extract_dimensions()
                self.metadata = {"width": w, "height": h}
                super().save()
            except Exception:
                pass  # don't block uploads on analysis failures
        return result
```

The pattern is: store first, analyze second, swallow analysis failures so a flaky analyzer can't break uploads.

For metadata that you'd want to *query* against (uploaded-by user id, gallery id, expiration date), add a real column to your `Attachment` subclass instead of stuffing it into `metadata`. JSON is fine for ad-hoc, optional data; a real column is better when it's queryable or required.

---

## Transforming Images

A *variant* is a derived file generated from an original. The classic case is a thumbnail: store one full-size avatar, but render a 200x200 crop in lists, a 64x64 crop in headers, and a blurred hero version on the profile page. Each variant is itself an `Attachment` row, with `parent` set to the original and `variant_key` set to a hash of the operations that produced it.

**Varriants are disabled by default**. To enable them, edit the `VARIANTS_ENABLED_FOR` in your `Attachhment` model to uncomment the `"image/*"` key:

```python {hl_lines="3-4"}
    class Attachment(app.attachment_for(BaseModel)):
        
        VARIANTS_ENABLED_FOR: dict[str, str] = {
            "image/*": "preview_image",
        }
```

You will also have install the system library `libvips` and the python package `pyvips`. See the [requirements section](#requirements) for details.

Variants are:

- **On-demand** - the variant file is generated the first time you ask for it, not at upload time.
- **Cached forever** - subsequent calls return the existing row without reprocessing.
- **Persisted** - both the bytes (in the active service) and the row (in the `attachment` table) are kept.

Variants are not free. The first request that triggers a new variant pays for the whole transformation (decode, resize, encode, upload). For predictable response times in production, pre-generate the variants you know you'll need - see [Eager Loading Variants](#eager-loading-variants).

### Generating a Variant

Call `variant(**ops)` on any attachment (with variants enabled):

```python
thumb = user.photo.variant(resize_to_fill=(200, 200))
thumb.url
# => "/storage/aBcDe..."
```

The first call processes the image and creates a new `Attachment` row. Subsequent calls with the same operations look up the existing row by hash and return it.

Variants inherit the parent's `service_name` unless you override it, so they land in the same service - and inherit its access mode automatically. A parent in a public service gives a public variant; a parent in a private service gives a signed variant. The variant's id is its own UUID.

In a template, calling `variant()` is cheap once the variant exists - it's a single index lookup by hash, not a recompute - so you can put it directly in the markup without caching gymnastics.

### Available Transformations

Pass any combination of these as keyword arguments to `variant()`:

Operation         | Args              | What it does
----------------- | ----------------- | --------------------
`resize_to_fit`   | `(width, height)` | Fit inside the box, preserving aspect ratio. Bigger images are downscaled, smaller images upscaled.
`resize_to_limit` | `(width, height)` | Like `resize_to_fit`, but smaller images are not upscaled.
`resize`          | `(width, height)` | Alias for `resize_to_limit`.
`resize_to_fill`  | `(width, height)` | Fill the box exactly, cropping the longer side. Center crop by default.
`resize_and_pad`  | `(width, height)` | Fit, then pad with black or transparent to reach the exact box.
`rotate`          | `(degrees)`       | Rotate by an arbitrary angle. Corners are filled with black by default.
`fliphor`         | `()`              | Flip horizontally.
`flipver`         | `()`              | Flip vertically.
`grayscale`       | `()` or `(r,g,b)` | Convert to grayscale. Default uses BT.601 luminance weights.
`sepia`           | `()` or `(r,g,b)` | Apply a sepia tone. Defaults produce a classic warm sepia.
`blur`            | `(sigma)`         | Gaussian blur. Larger sigma means more blur.
`composite`       | `(overlay)`       | Blend an overlay image on top - useful for watermarks.

Either `width` and/or `height` can be `None`.

Each operation accepts a positional tuple optionally ending with a kwargs dict for advanced settings:

```python
attachment.variant(resize_to_fill=(400, 400))
# smart crop
attachment.variant(resize_to_fill=(400, 400, {"crop": "attention"}))

# use an empty tuple for no args
attachment.variant(blur=())

# white corners
attachment.variant(rotate=(45, {"background": [255, 255, 255]}))

# bottom-right watermark
attachment.variant(composite=("logo.png", {"gravity": "south-east"}))
```

The full set of pyvips settings is forwarded through; the [pyvips documentation](https://www.libvips.org/API/current/){target=_blank} is the reference for what each operation supports.

You can chain operations in a single call - they're applied left to right (up to down, in this example):

```python
hero = post.cover_image.variant(
    resize_to_fill=(1600, 600),
    blur=(8.0,),
)
```


### Format Conversion

Two special keys, `load` and `save`, control how the image is read and written:

```python
# Load options - passed to pyvips when opening the file:
attachment.variant(
    resize_to_fit=(800, 600),
    load={"autorot": True},  # respect EXIF orientation (the default)
)

# Save options - passed to pyvips when writing the variant:
attachment.variant(
    resize_to_fit=(800, 600),
    save={"format": ".webp", "Q": 80},
)
```

When you don't pass `save["format"]`, Proper picks one for you based on the source content type:

1. If the source matches a pattern in `STORAGE_ALLOWED_VARIANTS` ([Baseline Configuration](#baseline-configuration)), the variant is saved in the **source format**. A JPEG source produces a JPEG variant, a PNG source produces a PNG variant.
2. Otherwise, the variant is saved in `STORAGE_FALLBACK_FORMAT` (default `"png"`). This covers source formats like TIFF, BMP, or HEIC that you don't want to expose verbatim.

A caller-supplied `save={"format": "..."}` overrides both rules. The format string controls both the file extension and the pyvips encoder; per-encoder options (quality, compression level, ...) are forwarded as additional keys in the same `save` dict.

### Variant Idempotency

`variant()` is idempotent: same arguments, same variant. The mechanism is a SHA-256 hash of the ops dict, stored as `variant_key` on the variant row. When you call `variant()`, Proper:

1. Resolves the save format (per the rules in [Format Conversion](#format-conversion)) and injects it into the ops dict.
2. Computes the SHA-256 hash from the resolved ops.
3. Looks up `Attachment.parent == self AND variant_key == hash`.
4. Returns the existing row if found, otherwise generates the variant and inserts a new row.

The resolved format is part of the hash, so a JPEG source with `resize_to_fill=(200, 200)` and a TIFF source with the same kwargs produce different keys (and different variants - the TIFF lands as PNG).

The argument *order* matters for the hash (`(200, 100)` is not the same as `(100, 200)`), but the order of keys *within* the `load` and `save` dicts does not - those are sorted before hashing.

This means you can call `variant()` freely in templates without worrying about duplicate work:

```html+jinja
{% for user in users %}
  <img src="{{ user.photo.variant(resize_to_fill=(64, 64)).url }}">
{% endfor %}
```

Each iteration looks up the same variant by hash. One database query per call, no reprocessing.

### Purging Variants

Call `purge_variants()` to delete every variant of an attachment, leaving the original in place:

```python
attachment.purge_variants()        # synchronous
attachment.purge_variants_later()  # queue a Huey task
```

You'd typically do this after a design change that invalidates dimensions (the 200x200 thumbnail is now 240x240 everywhere, regenerate), or in a migration that switches output format (move from JPEG to WebP variants).

`purge()` (without `_variants`) deletes the original *and* all of its variants in one call.

### Eager Loading Variants

In production you usually want to avoid the "first request pays" cost. Two common patterns:

**A. Pre-generate after upload.** Right after an attachment is saved, queue the variants you'll need:

```python
@app.queue.task
def generate_avatar_variants(attachment_id):
    att = Attachment.get_or_none(Attachment.id == attachment_id)
    if att is None:
        return
    att.variant(resize_to_fill=(64, 64))
    att.variant(resize_to_fill=(200, 200))
    att.variant(resize_to_fill=(800, 800))


def update(self):
    self.form.save()
    if self.user.photo_id:
        generate_avatar_variants(str(self.user.photo_id))
    self.response.redirect_to("User.show", self.user)
```

The first request that displays an avatar finds the variant already in the database and serves it without recomputing.

**B. Pre-generate in a migration.** When you add a new variant size to your design, walk the existing attachments and generate the new variant once:

```python
# scripts/backfill_variants.py
from myapp.models import User

for user in User.select().where(User.photo_id.is_null(False)):
    user.photo.variant(resize_to_fill=(64, 64))
```

Run it once after deploying the design change.

The variant cache (the row in `attachment` plus the bytes in the service) survives across requests, processes, and deploys. You only pay the generation cost once per (parent, ops) combination ever.

---

## Previewing Files

`variant()` can only handles images. For everything else - PDFs, videos, audio with cover art, ePubs - you need a way to extract an image "preview" of the file first.

The `VARIANTS_ENABLED_FOR` property of your `Attachment` model, maps content-type patterns with the names of methods on the same class, that generates that preview.

```python
VARIANTS_ENABLED_FOR = {
    "image/*": "preview_image",
    # "application/pdf": "preview_pdf",
    # "video/*": "preview_video",
}
```

:::warning
All three preview methods require libvips + pyvips:

- Images: libvips + pyvips
- PDFs: libvips + pyvips + [poppler](https://poppler.freedesktop.org/)
- Videos: libvips + pyvips + [ffmpeg](https://ffmpeg.org/)
:::


### PDF previews

PDF previews ship with the framework. To enable them, uncomment the `"application/pdf"` line in `VARIANTS_ENABLED_FOR` and install [poppler](https://poppler.freedesktop.org/) (`brew install poppler` on macOS, `apt install poppler-utils` on Debian/Ubuntu):

```python
# models/attachment.py
from ..main import app
from .base import BaseModel


class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        "application/pdf": "preview_pdf",
        # ...
    }
```

`pdf_attachment.variant(resize_to_fit=(400, 400))` produces a PNG thumbnail of the first page, stored as a normal variant - cached, deduplicated, served through whatever service the parent uses.

Two kwargs are specific to `preview_pdf`:

- `page=1` - 1-indexed page number to render. Pass `page=2` to preview the second page.
- `dpi=150` - render resolution in dots per inch. Bump to `dpi=300` when the source page is dense or when the final variant downscales by a large factor.

Both participate in the variant cache key, so `variant(page=1)` and `variant(page=2)` produce distinct cached variants.

### Video previews

Video previews ship with the framework. To enable them, uncomment the `"video/*"` line in `VARIANTS_ENABLED_FOR` and install [ffmpeg](https://ffmpeg.org/) (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Debian/Ubuntu):

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        "video/*": "preview_video",
        # ...
    }
```

`video_attachment.variant(resize_to_fit=(400, 400))` produces a PNG thumbnail of a single frame/

One kwarg is specific to `preview_video`:

- `at_seconds=1.0` - timestamp (in seconds) of the frame to extract. The default skips the first second to avoid black opening frames. Pass any float for arbitrary seeking.

It participates in the variant cache key, so `variant(at_seconds=1)` and `variant(at_seconds=5)` produce distinct cached variants.

### Custom previewers

The same shape works for epub cover extraction, audio waveform thumbnails, or anything that can be transformed into an image.

Write a method that takes the attachment bytes plus options and returns the image bytes. Then, sdd the content-type pattern to `VARIANTS_ENABLED_FOR`:

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        "application/epub+zip": "preview_epub",
        # ...
    }

    def preview_epub(self, source: bytes, **ops) -> bytes:
        image_bytes = extract_cover(source)  # your extraction logic
        return image_bytes
```

The preview method shape is deliberately simple. Anything that can read bytes and produce bytes is a valid previewer.

The preview method receives all of the kwargs you passed to `variant()`, including the resolved `save` dict. If your transform produces bytes in a fixed format and ignores `save["format"]`, that's fine - the variant_filename is still derived from the resolved format and the bytes are written as-is. If you want the transform to honor format conversions, inspect `ops["save"]["format"]` and branch accordingly.

---

## Testing

The bundled `config/storage.py` defines a separate `test` service pointing at `temp/storage/`. The `STORAGE` selector switches to it when the environment is `"test"`, so the test suite never writes into your development storage folder.

```python
"test": {
    "type": "Disk",
    "root": "temp/storage",
}
```

This is the equivalent of giving your tests their own database: a clean, isolated, throwaway service whose contents you can wipe between tests without losing anything that mattered.

### Discarding Files Stored During Tests

A small autouse fixture wipes the folder between tests:

```python
# tests/conftest.py
import shutil
import pytest


@pytest.fixture(autouse=True)
def clean_storage(app):
    test_root = app.root_path.parent / "temp" / "storage"
    yield
    if test_root.exists():
        shutil.rmtree(test_root)
```

Mark it `autouse=True` to run on every test (the recommended default) or pull it in explicitly when only some tests upload files. Because the folder is recreated by the Disk service on first use, you don't need to set it up before the test runs - just clean up after.

If you prefer to clean *before* each test, swap the `yield` order:

```python
@pytest.fixture(autouse=True)
def clean_storage(app):
    test_root = app.root_path.parent / "temp" / "storage"
    if test_root.exists():
        shutil.rmtree(test_root)
    yield
```

For attachments built in a fixture (a fixture that loads a known set of users with avatars, for example), generate them once per session and let the fixture set up and tear down its own folder.

### Testing Against Cloud Services

For S3-backed code paths, [moto](https://docs.getmoto.org/){target=_blank} mocks the AWS API at the boto3 layer. Configure it as a fixture rather than baking it into the test storage config:

```python
# tests/conftest.py
import os
import pytest
from moto import mock_aws


@pytest.fixture()
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture()
def s3_storage(aws_credentials, app):
    with mock_aws():
        import boto3
        boto3.client("s3").create_bucket(Bucket="test-bucket")
        # Override the active service for the duration of the test:
        original = app.config["STORAGE"]
        app.config["STORAGE"] = "amazon"
        yield
        app.config["STORAGE"] = original
```

Tests that need the S3 code path opt in by depending on `s3_storage`; the rest keep using the disk service. moto starts and tears down a per-test in-memory S3 with no network calls.

For end-to-end tests that should hit a real bucket - smoke tests on staging, integration tests that exercise IAM policies - you can use Minio running on a docker container. Or point a test environment at a dedicated bucket and run them outside the unit-test loop. The S3 service has no special test mode of its own.

---

## Implementing support for other cloud Services

Proper ships with two services: `Disk` and `S3`. To add support for another one, subclass `proper.storage.services.Service` and implement these six methods:

```python
# myapp/storage/gcs.py
from proper.storage.services import Service

class GigaCloud(Service):
    def __init__(self, app, **config):
        ...

    def upload(self, upload, att):
        """Write the upload to the service.
        Sets `attachment.byte_size` along the way."""

    def download(self, att):
        """Read the file out of the service into memory."""

    def send_file(self, att, response, as_attachment=False):
        """Stream the file to the active response, with the
        right disposition."""

    def purge(self, att):
        """Delete the file from the service. Trailing empty
        directories may also go."""

    def service_url(self, att, *, as_attachment=False):
        """Generates a short-lived signed URL for the file"""

    def direct_upload_url(attachment, cheksum):
        """Generates a presigned PUT URL + headers where the
        browser uploads to directly"""

```

Once the class is imported anywhere in your app (a top-level import in `myapp/__init__.py` is the simplest place), the `type` value in the service config matches the class name:

```python
STORAGE_SERVICES = {
    "giga": {
        "type": "GigaCloud",
        ...
    },
}
STORAGE = "giga"
```


Look at [`proper/storage/services/disk.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/disk.py) and [`proper/storage/services/s3.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/s3.py) for working references. Both are short and cover all six methods plus their constructors.

For services with native streaming responses (presigned URLs, range requests), `send_file` is where you'd integrate with that machinery. The signature `(attachment, response, as_attachment)` is the contract; how you fulfill it is up to the service.

---

## What's Next

Storage touches forms, models, async tasks, and the asset pipeline. A few places to go from here:

- [`AttachmentField`](/docs/forms#attachmentfield) in the Forms guide - the full reference for `AttachmentField`, including the lifecycle table and transactional save semantics.
- [Rendering Forms - Attachment uploads](/docs/form_rendering#attachment-uploads) - the HTML side: `file_input()`, `destroy_input()`, and the `image_input.jx` component.
- [Models](/docs/models) and [Relationships](/docs/relationships) - the foreign-key patterns that connect your records to attachments.
- [Background Tasks](/docs/tasks) - the queue that runs `purge_later()`, `purge_variants_later()`, and any eager-loading task you write.
- [pyvips documentation](https://www.libvips.org/API/current/){target=_blank} - the full image-processing reference behind `transform_image`.
