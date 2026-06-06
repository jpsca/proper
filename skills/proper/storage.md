---
title: Storage
description: Storage addon — file uploads, Attachment model, S3/disk backends, variants, direct uploads
last_verified: 2026-05-29
---

# Proper Storage

Proper Storage is an installable addon that gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3 (and S3-compatible services like DigitalOcean Spaces or MinIO) and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest.

## Table of Contents

- [Setup](#setup)
- [Built-in Services](#built-in-services)
- [Public Services](#public-services)
- [Baseline Configuration](#baseline-configuration)
- [Attaching Files to Models](#attaching-files-to-models)
- [Serving Files](#serving-files)
- [Direct Uploads](#direct-uploads)
- [Downloading Files](#downloading-files)
- [Removing Files](#removing-files)
- [Variants](#variants)
- [Previewing Non-Image Files](#previewing-non-image-files)
- [Custom Services](#custom-services)

## Setup

Install the storage blueprint with:

```bash
proper install storage
proper db migrate
```

This sets up configuration in your application, creates the Attachment model, the serving controllers, and the `attachment` table Proper Storage needs.

The installer creates:

- `models/attachment.py` — your Attachment model
- `controllers/storage_controller.py` — three controllers (redirect, proxy, direct upload)
- `config/storage.py` — service configuration + baseline keys
- `views/file_input.jx`, `views/image_input.jx` — Jx components for file inputs
- CSS + Stimulus controllers for the file/image inputs

### The Attachment model

The generated model uses `app.attachment_for(BaseModel)` to build a parent class with all the storage fields automatically (you don't need to add any columns yourself):

```python
from ..main import app
from .base import BaseModel


class Attachment(app.attachment_for(BaseModel)):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)

    VARIANTS_ENABLED_FOR = {
        "image/*": "preview_image",
        # "application/pdf": "preview_pdf",
        # "video/*": "preview_video",
    }
```

The generated parent provides these fields:

Field            | Type                   | Description
---------------- | ---------------------- | ---------------------------------
`id`             | UUIDField              | Primary key. **No `default=uuid4`** — generated on `save()`, so `att.id is None` reliably means "not in the database yet"
`service_name`   | CharField(64)          | Which storage service holds the file
`filename`       | CharField(255)         | Parameterized filename (lowercased, special chars → dashes)
`content_type`   | CharField(64)          | MIME type (auto-detected from filename, fallback `application/octet-stream`)
`byte_size`      | IntegerField           | File size in bytes (populated by the service during `save()` — never pre-fill)
`created_at`     | DateTimeField          | Creation timestamp (UTC)
`metadata`       | JSONField              | Arbitrary metadata (nullable)
`parent`         | ForeignKeyField(self)  | Parent attachment for variants (nullable)
`variant_key`    | CharField(64)          | SHA-256 digest of the variant's transformations
`source`         | CharField(32)          | Where the upload came from. Default `"direct"`. Addons set their own values when they pre-upload with a different lifecycle policy
`pending`        | BooleanField           | True for pre-uploaded blobs that haven't been confirmed by a parent record's save. The rich_text sweeper purges rows that stay pending past a grace period

### Configuring services

Declare storage services in `config/storage.py`. The default config declares three services named `local`, `test`, and `amazon`:

```python
STORAGES = {
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
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "bucket": "...",
        "region": "...",  # e.g. 'us-east-1'
    },
}

STORAGE = "local"
if env == "prod":
    STORAGE = "amazon"
elif env == "test":
    STORAGE = "test"
```

`STORAGES` names the available services, `STORAGE` names the default service. Declare more services than you actively use if you like - services are instantiated lazily, on first use.

## Built-in Services

### Disk service

Stores files on the local filesystem. Files are organized using a two-level directory sharding based on the attachment UUID: `{root}/{id[:2]}/{id[2:4]}/{filename}`.

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

The `root` path is relative to your application's root directory. The directory is created automatically if it doesn't exist.

### S3 Service (Amazon S3 and S3-compatible APIs)

Stores files in Amazon S3 or any S3-compatible object storage.

```python
"amazon": {
    "type": "S3",
    "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "bucket": f"your_own_bucket-{env}",
    "region": "us-east-1",
}
```

Required AWS S3 permissions: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`. For direct uploads also: presigned PUT support (no extra permission needed).

Required dependency: `uv add boto3`.

If you want to use environment variables, standard SDK configuration files, profiles, IAM instance profiles, or task roles, omit the `access_key_id`, `secret_access_key`, and `region` keys; boto3 resolves them through its default credential chain.

To connect to an S3-compatible object storage API such as DigitalOcean Spaces, MinIO, Cloudflare R2, Wasabi, or Backblaze B2, provide the `endpoint`:

```python
"digitalocean": {
    "type": "S3",
    "endpoint": "https://nyc3.digitaloceanspaces.com",
    "access_key_id": os.getenv("DO_SPACES_KEY"),
    "secret_access_key": os.getenv("DO_SPACES_SECRET"),
    "bucket": f"your_own_bucket-{env}",
    "region": "nyc3",
}
```

Optional `url_expires_in` (default 300 seconds) controls the TTL of presigned GET and PUT URLs the service returns.

## Public Services

Public access is decided at the **service** level — there's no per-attachment `public` flag. Mark a service `public: True` and every attachment stored in it is reachable through a stable, unsigned URL:

```python
"public": {
    "type": "S3",
    "bucket": "my-public-bucket",
    "public": True,
    # ... credentials, region, etc.
},
```

To put a new attachment in a public service, pass `service_name=`:

```python
att = Attachment(upload, service_name="public")
att.save()

# Or through the form field:
avatar = f.AttachmentField(Attachment, service_name="public")
```

Behavior per backend:

- **S3** — uploads set `ACL: public-read`; `service_url()` returns the bucket's native path-style URL (`<endpoint>/<bucket>/<key>`) with no expiry or signature. Direct-upload URLs sign `ACL: public-read` so browser PUTs apply the ACL. The bucket itself must allow object-level ACLs (S3 "Object Ownership" set to `BucketOwnerPreferred` or `ObjectWriter`). For CloudFront / custom domain / virtual-hosted-style URLs, subclass `S3` and override `service_url()`.
- **Disk** — `public: True` is informational only (Disk has no native URL); the file is still served through `StorageRedirectController` / `StorageProxyController` with a stable signed-token URL.

The flag is also exposed to application code via `obj.service.public`, and `Attachment.get_public(pk)` returns `None` unless the attachment lives in a public service:

```python
obj = Attachment.get_public(pk)
if obj is None:
    raise NotFound
```

> **Tradeoff:** On a public service, the native URL serves whatever `Content-Type` was baked in at upload — disposition can't be overridden per-request the way presigned URLs do. For typical public assets browsers render inline based on `Content-Type`, which is usually what you want. If you need forced-download behaviour for a specific file, use `attachment.get_proxy_url()` instead (streams through the app with the correct disposition).

## Baseline Configuration

Three keys, all populated by the installer, control how files are served and how variants are encoded:

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

- **`STORAGE_ALLOWED_INLINE`** — glob patterns (`fnmatch`) for content types served inline (`Content-Disposition: inline`). Anything not matched is served with `attachment`, triggering a download.
- **`STORAGE_ALLOWED_VARIANTS`** — glob patterns for source content types whose format is **preserved** when generating a variant. A source PNG → PNG variant; a source JPEG → JPEG variant. Add `image/webp` or `image/avif` here if your application produces those.
- **`STORAGE_FALLBACK_FORMAT`** — format used for variants whose source content type isn't in `STORAGE_ALLOWED_VARIANTS`. Default `"png"`. Set to `"jpg"` or `"webp"` if smaller files matter more than fidelity. A caller-supplied `save={"format": "..."}` always overrides both rules.

## Attaching Files to Models

To attach files to a model, add a `ForeignKeyField` pointing to your Attachment model:

```python
import peewee as pw

from .base import BaseModel
from .attachment import Attachment


class User(BaseModel):
    name = pw.CharField()
    avatar = pw.ForeignKeyField(Attachment, null=True)
```

### Creating attachments from forms

The recommended path is `f.AttachmentField` from `proper.forms`. The field saves the upload, assigns the FK, replaces the previous attachment, and handles explicit removal — all from `form.save()`. See [forms.md#attachmentfield](forms.md#attachmentfield) for the full reference.

```python
from proper import forms as f

from [[app_name]].models import Attachment, User


class UserForm(f.Form):
    class Meta:
        orm_cls = User

    name = f.TextField()
    avatar = f.AttachmentField(Attachment, required=False)
```

```python
def update(self):
    user = self.form.save()
    self.response.redirect_to("User.show", user)
```

The matching template helpers are `form.avatar.file_input(...)` and `form.avatar.destroy_input(...)`; the storage blueprint also ships an `<ImageInput>` component that wires drag-and-drop, preview, and remove for image attachments.

### Creating attachments manually

For non-form scenarios (background jobs, API endpoints, importers), construct attachments directly:

```python
from io import BytesIO

# From in-memory bytes:
att = Attachment(BytesIO(data), filename="report.pdf", content_type="application/pdf")
att.save()

# From an open file:
with open("/tmp/photo.jpg", "rb") as fp:
    att = Attachment(fp, filename="photo.jpg")
    att.save()

# From a request part:
upload = self.request.form.get("avatar")
att = Attachment(upload)
att.save()

user = User.create(name="...", avatar=att)
```

The `Attachment` constructor accepts anything with a `read()` method — open files, `BytesIO`, request bodies, or the `MultipartPart` objects produced by the form parser.

**Order matters when assigning the FK**: build → `save()` → assign. The `id` column has no `default=uuid4`, so the UUID is generated when you call `save()`, not when you call `Attachment(...)`. That makes `attachment.id is None` truthfully signal "not in the database yet" so you can't accidentally set a foreign key to a UUID that points at no row.

### Constructor options

All options are keyword-only:

```python
attachment = Attachment(
    upload,
    service_name="amazon",       # override the default service
    filename="custom-name.jpg",  # override the detected filename
    content_type="image/jpeg",   # override the detected MIME type
)
```

## Serving Files

The `proper install storage` command creates three controllers in `controllers/storage_controller.py`:

- **`StorageRedirectController`** (`GET /storage/redirect/<token>/<filename>`) — serves files via 302 to the service's native URL (e.g. a presigned S3 link) when one exists, falling back to streaming through the app.
- **`StorageProxyController`** (`GET /storage/proxy/<token>/<filename>`) — always streams bytes through the app.
- **`DirectUploadController`** (`POST /storage/direct`, `PUT /storage/direct/<token>`) — handles the direct-upload protocol. See [Direct Uploads](#direct-uploads).

### URL helpers

Every saved attachment exposes:

```python
attachment.url                            # alias for get_redirect_url()
attachment.get_redirect_url()             # => "/storage/redirect/<token>/<filename>"
attachment.get_proxy_url()                # => "/storage/proxy/<token>/<filename>"

# Absolute URLs (with scheme + host) — for OpenGraph, emails, etc.
attachment.get_redirect_url(_full=True)
attachment.get_proxy_url(_full=True)
```

Both URLs embed a signed token tied to the attachment's PK. The controllers resolve them via `Attachment.get_signed(token, max_age=None, salt="redirect"|"proxy")`, so by default the URLs do not expire — they stay valid until your `SECRET_KEY` rotates. Pass a `max_age` (in seconds) to `get_signed()` from your own code to enforce expiry.

### Redirect vs proxy

`StorageRedirectController` (the default, used by `attachment.url`) calls `obj.service_url()`. For services that expose a native URL (S3, GCS, …) this returns a presigned URL and the controller issues a 302. For services without one (Disk), it falls back to streaming the bytes through the app.

Use `attachment.get_proxy_url()` (and `StorageProxyController`) when you specifically need a URL on your own domain — for CDN caching, app-controlled response headers, or auth gating beyond the signed token.

Both controllers set `skip_authentication = True` because the signed token IS the access credential. Add app-specific guards (per-user access checks, etc.) by editing the generated `show()` method in your project. For more granular gating, create a separate controller and use a custom salt:

```python
class DownloadController(AppController):
    def show(self):
        att = Attachment.get_signed(
            self.params["token"], salt="secret", max_age=None,
        )
        if not att:
            raise NotFound
        # extra checks ...
        service_url = att.service_url()
        if service_url:
            self.response.redirect_to(service_url)
        else:
            att.send_file()

# Generate URLs that route to it (pick a salt different from "redirect"):
document.secret_file.url_for("Download.show", salt="secret")
```

### Model-level serving helpers

- **`attachment.send_file()`** — streams the bytes through the current response.
- **`attachment.service_url()`** — returns the service's native URL (presigned S3 link, etc.) or `None` for services without one.

Both apply the inline/attachment disposition rules from `STORAGE_ALLOWED_INLINE` automatically. Call these from your controllers rather than `obj.service.send_file(...)` / `obj.service.service_url(...)` directly, so disposition stays consistent across paths.

### Content disposition

`STORAGE_ALLOWED_INLINE` decides inline vs. download (see [Baseline Configuration](#baseline-configuration)). Default covers `image/*`, `video/*`, `application/pdf` — exactly what browsers know how to display in place. Everything else gets `Content-Disposition: attachment` and a download dialog.

## Direct Uploads

The `DirectUploadController` lets clients (e.g. the Lexxy rich-text editor) upload bytes **before** the form is submitted: the editor POSTs metadata, gets back a URL + headers, and PUTs the bytes directly to storage (S3) or back to the app (Disk).

The flow:

1. Client POSTs `{"blob": {"filename": ..., "content_type": ..., "byte_size": ..., "checksum": "<base64-md5>"}}` to `POST /storage/direct`.
2. Server creates a pending `Attachment` row via `Attachment.create_pending_blob(...)` (sets `pending=True`, `source="direct"`) and asks the service for a `direct_upload_url(att, checksum=...)` envelope.
3. Server responds:
   ```json
   {
     "id": "...", "signed_id": "...", "attachable_sgid": "...",
     "filename": "...", "content_type": "...", "byte_size": ...,
     "previewable": true,
     "url": "/storage/redirect/...",
     "direct_upload": {"url": "...", "headers": {...}}
   }
   ```
4. Client PUTs the bytes to `direct_upload.url` with the supplied headers.
   - **S3**: presigned PUT URL → S3 directly.
   - **Disk**: `PUT /storage/direct/<token>` → app stores bytes via `DirectUploadController.update`, which calls `obj.service.upload(BytesIO(self.request.body), obj)`. The token uses salt `"upload"` (distinct from `"redirect"`/`"proxy"`/`"download"`) and a short TTL.
5. The row stays `pending=True` until a parent model's save confirms ownership (rich_text's `HasRichText` mixin does this automatically). If nothing confirms it, a sweep task purges it after the grace period.

`DirectUploadController` is rate-limited to 10 requests/minute per client out of the box. Tune via `rate_limit = {"to": N, "within": SECONDS}` on the controller.

## Downloading Files

```python
data = attachment.download()
```

Whole file materialized in memory — fine for images and small documents, inappropriate for multi-gigabyte uploads. For very large files, write a streaming controller that reads from the underlying service and pipes to the response.

## Removing Files

Two purge entry points; both delete the row + the file from the active service:

```python
attachment.purge()        # synchronous (CLI scripts, background jobs)
attachment.purge_later()  # enqueues a Huey task, returns immediately
```

`purge()` also purges every variant of the attachment first. `purge_later()` takes only the PK and re-fetches the row before acting, so it's safe even if the row is deleted some other way before the task runs.

`AttachmentField` uses `purge_later()` for the previous attachment after a successful replacement: new upload is saved synchronously (you want to know if that fails), cleanup of the old file happens in the background (a slow S3 delete shouldn't block the form response).

To remove just the variants, leaving the original:

```python
attachment.purge_variants()        # synchronous
attachment.purge_variants_later()  # background
```

## Variants

Variants are transformed versions of an attachment — thumbnails, resized images, format conversions, etc. They are stored as regular Attachment records with a foreign key back to the parent, so they get the full Attachment API (upload, download, send_file, purge, url) for free. They inherit the parent's `service_name` (and therefore its access mode) unless you override it.

Variants are identified by a SHA-256 hash of their transformations + resolved save format, stored as `variant_key`. Calling `variant()` with the same arguments is idempotent — it returns the existing variant instead of creating a duplicate. The transformations are also stored unhashed in `metadata["ops"]` for introspection.

> **Prerequisite:** Image variants require [libvips](https://www.libvips.org/install.html) and the `pyvips` Python package (`uv add pyvips`).

**Variants are disabled by default**. Enable them by setting `VARIANTS_ENABLED_FOR` on your Attachment model. The blueprint's generated `attachment.py` already has the `"image/*"` line uncommented.

### Using `variant()`

Call `variant(**ops)` on any saved attachment:

```python
thumb = attachment.variant(resize_to_fill=(400, 400))
thumb.url
```

Calling again with the same transformations returns the existing variant — single index lookup by hash, not a recompute. Safe to call in templates without caching gymnastics:

```html+jinja
{% for user in users %}
  <img src="{{ user.avatar.variant(resize_to_fill=(64, 64)).url }}">
{% endfor %}
```

Chain multiple operations — applied left to right:

```python
attachment.variant(
    resize_to_fit=(800, 800),
    rotate=(45,),
)
```

Inspect what produced a variant via its metadata:

```python
thumb.metadata["ops"]  # {"resize_to_fill": [400, 400], "save": {"format": "jpg"}}
```

If the content type doesn't match any `VARIANTS_ENABLED_FOR` pattern, `variant()` raises `ValueError`.

Check whether an attachment supports variants without trying:

```python
if attachment.is_previewable:
    thumb = attachment.variant(resize_to_limit=(200, 200))
```

### Available transformations

All resize operations preserve the aspect ratio and apply a mild sharpening. Options are forwarded to [`vips_thumbnail()`](https://www.libvips.org/API/current/ctor.Image.thumbnail.html).

Operation         | Args              | Notes
----------------- | ----------------- | --------------------
`resize_to_fit`   | `(w, h)`          | Fit inside the box. Either dimension can be `None`. Upsizes smaller images.
`resize_to_limit` | `(w, h)`          | Like `resize_to_fit`, but smaller images are not upscaled.
`resize`          | `(w, h)`          | Alias for `resize_to_limit`.
`resize_to_fill`  | `(w, h)`          | Fill exactly, crop the longer side. Center crop by default. Pass `(w, h, "attention")` for smart crop.
`resize_and_pad`  | `(w, h)`          | Fit, then pad. Black by default (or transparent if source has alpha).
`rotate`          | `(degrees)`       | Non-90° fills corners with black (override with `{"background": [r,g,b]}`).
`fliphor`         | `()`              | Flip horizontally.
`flipver`         | `()`              | Flip vertically.
`grayscale`       | `()` or `(r,g,b)` | Default BT.601 perceptual weights. Custom triple lets you do channel-only filters.
`sepia`           | `()` or `(r,g,b)` | Defaults to a classic warm sepia.
`blur`            | `(sigma)`         | Gaussian blur. Larger sigma → more blur.
`composite`       | `(overlay_path)`  | Blend an image (watermark). Pass `{"gravity": "south-east", "offset": [10,10]}` to position.

Each operation accepts a positional tuple optionally ending with a kwargs dict for advanced settings:

```python
attachment.variant(resize_to_fill=(400, 400, {"crop": "attention"}))
attachment.variant(rotate=(45, {"background": [255, 255, 255]}))
attachment.variant(composite=("logo.png", {"gravity": "south-east"}))
```

### `load` and `save` options

`load` is forwarded to `pyvips.Image.new_from_file()` (controls how the source is read; `autorot=True` is default). `save` is forwarded to `pyvips.Image.write_to_buffer()`:

```python
attachment.variant(
    resize_to_fit=(800, 800),
    load={"autorot": False},                  # ignore EXIF orientation
)
attachment.variant(
    resize_to_fill=(400, 400),
    save={"format": ".webp", "Q": 80},        # explicit format + quality
)
```

When `save["format"]` is not provided, Proper picks one:

1. If the source content type matches `STORAGE_ALLOWED_VARIANTS` (see [Baseline Configuration](#baseline-configuration)), preserve the **source format**.
2. Otherwise, use `STORAGE_FALLBACK_FORMAT` (default `"png"`).

The resolved format is included in `variant_key`, so a JPEG source and a TIFF source with the same kwargs produce **different** variants (one stays JPEG, the other becomes PNG).

The argument order within `variant()` matters for the hash (`(200, 100)` ≠ `(100, 200)`), but keys *within* `load` and `save` dicts are sorted before hashing.

### Iterating and purging variants

```python
for v in attachment.variants:
    print(v.variant_key, v.url)

attachment.purge()                  # purges variants + parent
attachment.purge_variants()         # variants only, parent stays
attachment.purge_variants_later()   # queues a Huey task
```

You'd typically `purge_variants()` after a design change that invalidates dimensions, or in a migration that switches output format.

### Eager-loading variants

In production you usually want to avoid the "first request pays" cost. Pre-generate the variants you'll need from a Huey task right after the upload:

```python
@app.queue.task
def generate_avatar_variants(attachment_id):
    att = Attachment.get_or_none(Attachment.id == attachment_id)
    if att is None:
        return
    att.variant(resize_to_fill=(64, 64))
    att.variant(resize_to_fill=(200, 200))

def update(self):
    self.form.save()
    if self.user.avatar_id:
        generate_avatar_variants(str(self.user.avatar_id))
    self.response.redirect_to("User.show", self.user)
```

Or backfill in a migration when you add a new size. The variant cache survives across requests, processes, and deploys.

### Low-level variant creation

For full control, use `create_variant(upload, **kwargs)`. It inherits `service_name` from the parent by default:

```python
thumb = attachment.create_variant(thumbnail_data)
webp = attachment.create_variant(
    converted_file,
    content_type="image/webp",
    filename="photo.webp",
)
```

## Previewing Non-Image Files

`variant()` can only handle images. For PDFs, videos, etc., you need a method that extracts an image "preview" of the file first. The framework ships `preview_pdf` (poppler's `pdftoppm`) and `preview_video` (ffmpeg). Both are one-line enables plus the system tool.

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        "image/*": "preview_image",
        "application/pdf": "preview_pdf",    # install poppler
        "video/*": "preview_video",          # install ffmpeg
    }
```

System tool installation:

- **libvips** (images): `brew install vips` / `apt install libvips-dev`
- **poppler** (PDFs): `brew install poppler` / `apt install poppler-utils`
- **ffmpeg** (videos): `brew install ffmpeg` / `apt install ffmpeg`

Preview methods accept extra kwargs that participate in the variant cache key (so different pages/timestamps cache independently):

- `preview_pdf(..., page=1, dpi=150)`
- `preview_video(..., at_seconds=1.0)`

```python
pdf_attachment.variant(resize_to_fit=(400, 400), page=2, dpi=300)
video_attachment.variant(resize_to_fit=(400, 400), at_seconds=5.0)
```

### Custom previewers

Extend `VARIANTS_ENABLED_FOR` and add a method with the signature `(source: bytes, **ops) -> bytes` that returns the extracted image bytes. The framework then runs the result through `transform_image(image_bytes, **ops)` for any resize / format-conversion ops:

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        "image/*": "preview_image",
        "application/epub+zip": "preview_epub",
    }

    def preview_epub(self, source: bytes, **ops) -> bytes:
        return extract_cover(source)  # your extraction logic
```

The method receives all of the kwargs passed to `variant()`, including the resolved `save` dict — branch on `ops["save"]["format"]` if you want the transform to honor format conversions.

## Custom Services

To add your own storage service, subclass `proper.storage.Service` and implement **six** methods:

```python
from proper.storage import Service


class GoogleCloud(Service):
    def __init__(self, app, **config):
        self.bucket_name = config.pop("bucket")
        # ... initialize client ...
        super().__init__(app, **config)

    def upload(self, upload, att):
        """Write the upload to the service. Sets att.byte_size along the way."""

    def download(self, att) -> bytes:
        """Read the file out of the service into memory."""

    def send_file(self, att, response, as_attachment=False):
        """Stream the file to the active response, with the right disposition."""

    def purge(self, att):
        """Delete the file from the service."""

    def service_url(self, att, *, as_attachment=False) -> "str | None":
        """Short-lived signed GET URL, or None if the service has no native URL."""

    def direct_upload_url(self, att, *, checksum="") -> dict:
        """Return {'url': '...', 'headers': {'Content-Type': '...', ...}}.
        For remote services: a presigned PUT URL the browser uploads to directly.
        For local services: the app's own bytes-receiving endpoint.
        If `checksum` (base64 MD5) is supplied, propagate as Content-MD5.
        """
```

Then add a config entry where the `type` matches your class name:

```python
STORAGES = {
    "gcs": {
        "type": "GoogleCloud",
        "bucket": "my-bucket",
        "project": "my-project",
    },
}
STORAGE = "gcs"
```

The base class handles the `public` config key in `__init__`, so subclasses just need to call `super().__init__(app, **config)` last and consult `self.public` from `upload()` / `service_url()` / `direct_upload_url()` if they support a public mode (see `proper/storage/services/s3.py` for the reference implementation).

Service instances are cached per `Attachment` class, so initialization only happens once per service name.

[`proper/storage/services/disk.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/disk.py) and [`proper/storage/services/s3.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/s3.py) are short and cover all six methods plus their constructors.
