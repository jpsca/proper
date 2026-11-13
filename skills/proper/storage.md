---
title: Storage
description: Storage addon: setup, Disk and S3 services, public services, attaching files to models (forms and manual), serving (redirect vs proxy, URL helpers), direct uploads, downloading and removing
last_verified: 2026-11-13
sources:
  - src/proper/storage
  - src/proper/tools/storage.py
  - src/proper/_blueprints/addon_storage
---

# Storage

Proper Storage is an installable addon that gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3 (and S3-compatible services like DigitalOcean Spaces or MinIO) and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest.

Variants (resized images), previews of non-image files and custom services are in [storage_advanced.md](storage_advanced.md).

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
- [Variants, Previews and Custom Services](#variants-previews-and-custom-services)


## Setup

Install the storage blueprint with:

```bash
proper install storage
proper db migrate
```

This sets up configuration in your application, creates the Attachment model and the serving controllers, adds `pyvips` to the dependencies, and writes the migration of the `attachment` and `attachment_reference` tables (`proper db create "storage"`), which `proper db migrate` applies.

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
    # You can add any extra fields here
    # creator = pw.ForeignKeyField(User, null=True, backref="attachments")

    VARIANTS_ENABLED_FOR = (
        ("image/*", "preview_image"),
        # ("application/pdf", "preview_pdf"),
        # ("video/*", "preview_video"),
    )
```

The generated parent provides these fields:

Field            | Type                   | Description
---------------- | ---------------------- | ---------------------------------
`id`             | CharField(32)          | Primary key, a UUID4 hex string. **No default**: generated on `save()`, so `att.id is None` reliably means "not in the database yet"
`service_name`   | CharField(64)          | Which storage service holds the file
`filename`       | CharField(255)         | Parameterized filename (lowercased, special chars → dashes)
`content_type`   | CharField(64)          | MIME type: the upload's own `content_type` if it has one, else guessed from the filename, else `application/octet-stream`
`byte_size`      | IntegerField           | File size in bytes, set by the service during `save()`. A direct upload starts with the size the client declared; on Disk, `DirectUploadController.update` saves the real one, while an S3 upload never reaches the app, so its row keeps the declared size
`created_at`     | DateTimeField          | Creation timestamp (UTC)
`metadata`       | pw.JSONField           | Arbitrary metadata (nullable)
`parent`         | ForeignKeyField(self)  | Parent attachment for variants (nullable)
`variant_key`    | CharField(64)          | SHA-256 digest of the variant's transformations
`source`         | CharField(32)          | Where the upload came from. Empty (the default) for a file sent with a form or attached from code; `"rich_text"` for an upload of the rich text editor. Addons set their own values when they pre-upload with a different lifecycle policy

And two attributes about the records that embed the attachment in a rich text field (see [Rich Text](rich_text.md#attachment-lifecycle)): `is_referenced` (bool) and `references` (the rows of `Attachment.Reference`).

`attachment_for()` also builds `Attachment.Reference`, the model of those rows (table `attachment_reference`: `attachment` FK with `ON DELETE CASCADE`, `record_type`, `record_id`, `field`, unique together). The generated `models/attachment.py` exports it as `AttachmentReference`, so `proper db create` makes its table. Only the rich text addon adds rows to it (`purge()` deletes them).

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

Stores files on the local filesystem. Files are organized by the attachment id: `{root}/{id[:2]}/{id[2:4]}/{id}/{filename}`. The full id is a directory, so two files with the same name never collide; the filename is ASCII-sanitized with `secure_filename()`.

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

The `root` path is relative to the project root (the directory that contains your app package). The directory is created automatically if it doesn't exist.

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

Required AWS S3 permissions: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, and `s3:PutObjectAcl` for a service with `public: True` (its uploads send `ACL: public-read`). For direct uploads also: presigned PUT support (no extra permission needed).

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
- **Disk** — Disk has no native URL, so the file is still served through `StorageRedirectController` / `StorageProxyController` with a stable signed-token URL. `public: True` changes the caching policy of those responses from `private` to `public` (see [Caching](#caching)), so a CDN or reverse proxy in front of your app may cache them.

The flag is also exposed to application code via `obj.service.public`, and `Attachment.get_public(pk)` returns `None` unless the attachment lives in a public service:

```python
obj = Attachment.get_public(pk)
if obj is None:
    raise NotFound
```

> **Tradeoff:** On a public service, the native URL serves whatever `Content-Type` was baked in at upload — disposition can't be overridden per-request the way presigned URLs do. For typical public assets browsers render inline based on `Content-Type`, which is usually what you want. `attachment.get_proxy_url()` streams through the app and applies `STORAGE_ALLOWED_INLINE`, which the native public URL ignores. There is no per-file override: to force a download of one file, write a controller that calls `att.service.send_file(att, response=self.response, as_attachment=True)`.


## Baseline Configuration

These keys control how files are served and how variants are made. All have framework defaults; the installer writes `STORAGE_ALLOWED_INLINE`, `STORAGE_ALLOWED_VARIANTS`, `STORAGE_FALLBACK_FORMAT` and `STORAGE_SAFE_IMAGE_LOADERS` into `config/storage.py`:

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

- **`STORAGE_SAFE_IMAGE_LOADERS`** — prefixes of the libvips loader class names allowed when making variants (default: JPEG, PNG, WebP, GIF, TIFF, HEIF). Every other loader is blocked: the SVG loader reads local files and the ImageMagick delegate can run code. Add a prefix (e.g. `"VipsForeignLoadJxl"`) to allow another format.
- **`STORAGE_MAX_IMAGE_PIXELS`** — the most pixels (width × height) of an image a variant is made from (default `100_000_000`; `None` for no limit). Checked from the header, before decoding: a decompression bomb raises `proper.storage.imageops.ImageTooLarge` (a `ValueError`).
- **`STORAGE_ALLOWED_INLINE`** — glob patterns (`fnmatch`) for content types served inline (`Content-Disposition: inline`). Anything not matched is served with `attachment`, triggering a download.
- `attachment.send_file()` also sends `X-Content-Type-Options: nosniff` and, for every type but `application/pdf`, `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox` (`Attachment.SANDBOX_POLICY`): an uploaded SVG or HTML with a script opened by its URL doesn't run it, and has no access to the app's origin. Chrome's PDF viewer doesn't run in a sandbox. A presigned S3 URL (`service_url()`) is another origin, and gets the headers S3 sends.
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

The recommended path is `f.AttachmentField` from `proper.forms`. The field saves the upload, assigns the FK, replaces the previous attachment, and handles explicit removal — all from `form.save()`. See [reference/form_fields.md#attachmentfield](reference/form_fields.md#attachmentfield) for the full reference.

```python
from proper import forms as f

from myapp.models import Attachment, User


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

The matching template helpers are `form.avatar.file_input(...)` and `form.avatar.destroy_input(...)`, plus `form.avatar.attachment`: the saved attachment to show, or `None` (don't use `form.avatar.value` for that: after a failed validation it is the upload, which has no `url`); the storage blueprint also ships an `<ImageInput>` component that wires drag-and-drop, preview, and remove for image attachments.

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

The `Attachment` constructor accepts a seekable binary file object (`read`/`seek`/`tell`: open files, `BytesIO`, `SpooledTemporaryFile`) or a `MultipartPart` from the form parser (its `.file` is used).

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
- **`StorageProxyController`** (`GET /storage/proxy/<token>/<filename>`) — sends the bytes through the app. The Disk service streams the file; the S3 service downloads the whole object into memory first, so for large S3 files prefer the redirect.
- **`DirectUploadController`** (`POST /storage/direct`, `PUT` or `PATCH /storage/direct/<token>`) — handles the direct-upload protocol. See [Direct Uploads](#direct-uploads).

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

Both URLs embed a signed token tied to the attachment's PK. The controllers resolve them via `Attachment.get_signed(token, max_age=None, salt="redirect"|"proxy")` (`get_signed()` defaults to `max_age=YEAR`; `None` accepts the stable tokens), so the URLs do not expire — they stay valid until your `SECRET_KEY` rotates.

**These two URLs are stable**: the token has no timestamp (`generate_token(timed=False)`), so the same attachment always gives the same URL. That is what lets browsers cache the file; a URL that changes on every render never gets a cache hit. URLs generated before this existed (timed tokens) keep resolving.

**Custom URLs are timed by default.** `attachment.url_for("Download.show", salt="secret")` gives a different URL on every call, and your controller can expire it with `get_signed(token, salt="secret", max_age=...)`. Pass `stable=True` to `url_for()` to get a stable one instead; a stable token can't prove its age, so it only resolves with `max_age=None`.

### Caching

`attachment.send_file()` (used by both generated controllers) sets `Cache-Control: private, max-age=31536000, immutable`. The bytes of an attachment never change (replacements and variants are new rows), so the long lifetime is safe. It says `public` instead of `private` when the storage service has `public: True`, which also allows shared caches (CDN, reverse proxy) to keep a copy; keep it `private` for anything gated by the token or by controller-level checks. Override `CACHE_MAX_AGE` on your `Attachment` model to change the duration, or set it to `None` to send no caching headers. Redirects to presigned S3 URLs are not affected.

### Redirect vs proxy

`StorageRedirectController` (the default, used by `attachment.url`) calls `obj.service_url()`. For services that expose a native URL (S3, GCS, …) this returns a presigned URL and the controller issues a 302. For services without one (Disk), it falls back to streaming the bytes through the app.

Use `attachment.get_proxy_url()` (and `StorageProxyController`) when you specifically need a URL on your own domain — for CDN caching, app-controlled response headers, or auth gating beyond the signed token.

Both controllers set `skip_authentication = True` because the signed token IS the access credential. Add app-specific guards (per-user access checks, etc.) by editing the generated `show()` methods in your project: comments in the generated file mark the spot. `Attachment` has no owner column, so an app where users must not see each other's files adds one (the generated model has a commented `creator` field), sets it where the attachment is created (`Attachment.create_pending_blob(..., source=self.source, creator=current.user)` in `DirectUploadController.create` for editor uploads: extra keyword arguments become column values) and compares it with `current.user` in `show()` and in `DirectUploadController.update` (a commented check marks the spot); `current.user` is loaded on public actions too. The check means nothing for a service with `public: True`, whose bucket URL is open anyway. For more granular gating, create a separate controller and use a custom salt:

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
2. Server creates an `Attachment` row via `Attachment.create_pending_blob(..., source=self.source)` (metadata only; extra keyword arguments become column values) and asks the service for a `direct_upload_url(att, checksum=...)` envelope. `source` is a class attribute of the controller, `"rich_text"`; the client can't choose it.
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
   - **Disk**: `PUT /storage/direct/<token>` → app stores bytes via `DirectUploadController.update`, which calls `obj.service.upload(BytesIO(self.request.body), obj)`. The token uses salt `"upload"` (distinct from `"redirect"`/`"proxy"`) and expires after 15 minutes (`resolve_token()`'s default `max_age`).
5. The row has no references until a parent model's save records that it embeds it (rich_text's `HasRichText` mixin does this automatically). If nothing ever embeds it, the rich text addon's sweep task purges it after the grace period (24 hours by default); with only the storage addon, nothing sweeps it.

`DirectUploadController` is rate-limited to 10 requests/minute per IP address out of the box, counting every action: on Disk, the `POST` and the `PUT` of one upload are two (needs a configured cache; without one no limit applies). Tune via `rate_limit = {"to": N, "within": SECONDS, "by": ...}` on the controller. Unlike the two serving controllers, it does not set `skip_authentication`, so with the auth addon installed direct uploads need a signed-in user.


## Downloading Files

```python
data = attachment.download()
```

Whole file materialized in memory — fine for images and small documents, inappropriate for multi-gigabyte uploads. For very large files, write a streaming controller that reads from the underlying service and pipes to the response.


## Removing Files

`delete_instance()` deletes only the row; the file stays in its service. Two purge entry points delete the file from the attachment's own service and then the row:

```python
attachment.purge()        # synchronous (CLI scripts, background jobs)
attachment.purge_later()  # enqueues a Huey task, returns immediately
```

`purge()` also purges every variant (each from its own service) and deletes the references of the records that embed the attachment before deleting the row. `purge_later()` takes only the PK and re-fetches the row before acting, so it's safe even if the row is deleted some other way before the task runs.

`AttachmentField` uses `purge_later()` for the previous attachment after a successful replacement: new upload is saved synchronously (you want to know if that fails), cleanup of the old file happens in the background (a slow S3 delete shouldn't block the form response).

To remove just the variants, leaving the original:

```python
attachment.purge_variants()        # synchronous
attachment.purge_variants_later()  # background
```


## Variants, Previews and Custom Services

Resized or converted versions of an attachment (`attachment.variant(...)`), previews of PDFs and videos, and writing a storage service of your own are in [storage_advanced.md](storage_advanced.md).
