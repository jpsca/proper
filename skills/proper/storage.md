---
title: Storage
description: Storage addon — file uploads, Attachment model, S3/disk backends, variants
last_verified: 2026-05-27
---

# Proper Storage

Proper Storage is an installable addon that gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3 (and S3-compatible services like DigitalOcean Spaces or MinIO) and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest.

## Table of Contents

- [Setup](#setup)
- [Built-in Services](#built-in-services)
- [Attaching Files to Models](#attaching-files-to-models)
- [Serving Files](#serving-files)
- [Downloading Files](#downloading-files)
- [Removing Files](#removing-files)
- [Variants](#variants)
- [Custom Services](#custom-services)

## Setup

Install the storage blueprint with:

```bash
proper install storage
proper db migrate
```

This sets up configuration in your application, creates the Attachment model, the serving controllers, and the `attachment` table Proper Storage needs.

The installer creates three files:

- `models/attachment.py` — your Attachment model
- `controllers/storage_controller.py` — controllers for serving files
- `config/storage.py` — service configuration


### The Attachment model

The generated model uses `app.attachment_for(BaseModel)` to build a parent class with all the storage fields automatically (you don't need to add any columns yourself):

```python
from ..main import app
from .base import BaseModel


class Attachment(app.attachment_for(BaseModel)):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)
    ...
```

The generated parent provides these fields:

Field            | Type                   | Description
---------------- | ---------------------- | ---------------------------------
`id`             | UUIDField              | Primary key (auto-generated)
`service_name`   | CharField(64)          | Which storage service holds the file
`filename`       | CharField(255)         | Parameterized filename
`content_type`   | CharField(64)          | MIME type (auto-detected from filename)
`byte_size`      | IntegerField           | File size in bytes
`created_at`     | DateTimeField          | Creation timestamp (UTC)
`metadata`       | JSONField              | Arbitrary metadata (nullable)
`parent`         | ForeignKeyField(self)  | Parent attachment for variants (nullable)
`variant_key`    | CharField(64)          | SHA-256 digest of the variant's transformations

Mark a service `public: True` to flag attachments stored in it as publicly intended. This is an informational flag exposed to application code via `obj.service.public` and `Attachment.get_public(pk)` — the framework's URL helpers and controllers treat public and private attachments the same. See "Public services" under [Serving Files](#serving-files).


### Configuring services

Declare storage services in `config/storage.py`. For each service your application uses, provide a name and its configuration. The example below declares three services named `local`, `test`, and `amazon`:

```python
STORAGE_SERVICES = {
    "local": {
        "type": "Disk",
        "root": "storage/",
    },

    "test": {
        "type": "Disk",
        "root": "temp/storage",
    },

    # Replace with your real production service
    "amazon": {
        "type": "S3",
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "bucket": "...",
        "region": "...",  # e.g. 'us-east-1'
    },
}
```

Then, tell Proper Storage which service to use by setting the `STORAGE` config to the name of the service. Because each environment will likely use a different service, this is the default configuration:

```python
STORAGE = "local"
if env == "prod":
    STORAGE = "amazon"
elif env == "test":
    STORAGE = "test"
```

You probably want to use the `env` value in the bucket names to further reduce the risk of accidentally destroying production data:

```python
"amazon": {
    "type": "S3",
    "bucket": f"your_own_bucket-{env}",
    # ...
}
```


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

Required AWS S3 permissions: `s3:PutObject`, `s3:GetObject`, and `s3:DeleteObject`.

If you want to use environment variables, standard SDK configuration files, profiles, IAM instance profiles, or task roles, you can omit the `access_key_id`, `secret_access_key`, and `region` keys. The S3 Service supports all authentication options described in the [boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

To connect to an S3-compatible object storage API such as DigitalOcean Spaces or MinIO, provide the `endpoint`:

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


## Attaching Files to Models

To attach files to a model, add a `ForeignKeyField` pointing to your Attachment model:

```python
import peewee as pw

from .base import BaseModel
from .attachment import Attachment


class User(BaseModel):
    name = pw.CharField()
    avatar = pw.ForeignKeyField(Attachment, null=True)


class Article(BaseModel):
    title = pw.CharField()
    cover_image = pw.ForeignKeyField(Attachment, null=True)
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
def create(self):
    upload = self.request.form.get("avatar")
    attachment = Attachment(upload)
    attachment.save()

    user = User.create(
        name=self.request.form.get("name"),
        avatar=attachment,
    )
```

The `Attachment` constructor accepts a file object (a `MultipartPart` from a form upload or any `BinaryIO`) as its first argument. It automatically:

- Extracts and parameterizes the filename (lowercased, special characters replaced with dashes)
- Detects the MIME type from the file extension
- Uses the default storage service from your `STORAGE` config

When `save()` is called, the file is uploaded to the configured service and then the database record is persisted. If `save()` is called again later (e.g., to update metadata), the file is not re-uploaded.

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

To flag an attachment as publicly intended (for application-level access checks), store it in a service whose config has `public: True` by passing the corresponding `service_name`. The flag is informational — it doesn't change URL generation or routing.


## Serving Files

The `proper install storage` command creates three controllers in `controllers/storage_controller.py`:

- **`StorageRedirectController`** (`GET /storage/redirect/<token>`) — serves files via 302 to the service's native URL (e.g. a presigned S3 link) when one exists, falling back to streaming through the app.
- **`StorageProxyController`** (`GET /storage/proxy/<token>`) — always streams bytes through the app.
- **`DirectUploadController`** (`POST /storage/direct`, `PUT /storage/direct/<token>`) — handles the direct-upload protocol (browser metadata POST + bytes PUT for the Disk service).


### URL helpers

Every saved attachment exposes:

```python
attachment.url           # alias for `url_redirect`
attachment.url_redirect  # => "/storage/redirect/<signed-token>"
attachment.url_proxy     # => "/storage/proxy/<signed-token>"
```

Both URLs embed a signed token tied to the attachment's PK. The controllers resolve them via `Attachment.get_signed(token, max_age=None)`, so by default the URLs do not expire — they stay valid until your `SECRET_KEY` rotates. Pass a `max_age` (in seconds) to `get_signed()` from your own code to enforce expiry.


### Redirect vs proxy

`StorageRedirectController` (the default, used by `attachment.url`) calls `obj.service_url()`. For services that expose a native URL (S3, GCS, …) this returns a presigned URL and the controller issues a 302. For services without one (the Disk service), it falls back to streaming the bytes through the app:

```python
@router.resource("storage/redirect", pk="token")
class StorageRedirectController(AppController):
    skip_authentication = True

    def show(self):
        token = self.params.get("token")
        obj = Attachment.get_signed(token, max_age=None)
        if not obj:
            raise NotFound

        service_url = obj.service_url()
        if service_url:
            self.response.redirect_to(service_url)
        else:
            obj.send_file()
```

Use `attachment.url_proxy` (and `StorageProxyController`) when you specifically need a URL on your own domain — for CDN caching, app-controlled response headers, or auth gating beyond the signed token:

```python
@router.resource("storage/proxy", pk="token")
class StorageProxyController(AppController):
    skip_authentication = True

    def show(self):
        token = self.params.get("token")
        obj = Attachment.get_signed(token, max_age=None)
        if not obj:
            raise NotFound

        obj.send_file()
```

Both controllers set `skip_authentication = True` because the signed token IS the access credential. Add app-specific guards (per-user access checks, etc.) by editing the generated `show()` method in your project.


### Public services

Mark a service `public: True` to declare its objects publicly readable. The framework does not ship a separate public route — public-service attachments use the same `url` / `url_redirect` / `url_proxy` helpers and the same controllers as private ones. The behaviour difference happens inside the service:

- **S3** — uploads set `ACL: public-read`, and `service_url()` returns the bucket's native path-style URL (`<endpoint>/<bucket>/<key>`) with no expiry and no signature. Direct-upload URLs also sign `ACL: public-read` so browser PUTs apply the ACL. The bucket itself must allow object-level ACLs (S3 "Object Ownership" set to `BucketOwnerPreferred` or `ObjectWriter`). For CloudFront / custom domain / virtual-hosted-style URLs, subclass `S3` and override `service_url()`.
- **Disk** — `public: True` is informational only (Disk has no native URL); the file is still served through `StorageRedirectController` / `StorageProxyController` with a stable signed-token URL.

```python
"public": {
    "type": "S3",
    "bucket": "my-public-bucket",
    "public": True,
    # ... credentials, region, etc.
}
```

The flag is also exposed to application code. Read `obj.service.public` directly, or use `Attachment.get_public(pk)` for a guarded PK lookup that returns `None` unless the attachment lives in a public service:

```python
obj = Attachment.get_public(pk)
if obj is None:
    raise NotFound
```

> **Tradeoff:** On a public service, the native URL serves whatever `Content-Type` was baked in at upload — disposition can't be overridden per-request the way presigned URLs do. For typical public assets (avatars, hero images, PDFs) browsers render inline by default based on `Content-Type`, which is usually what you want. If you need forced-download behaviour for a specific file, use `attachment.url_proxy` instead (streams through the app with the correct disposition).


### Model-level serving helpers

The Attachment model exposes two serving helpers that apply the disposition rules from `STORAGE_ALLOWED_INLINE` automatically:

- **`attachment.send_file()`** — streams the bytes through the current response.
- **`attachment.service_url()`** — returns the service's native URL (presigned S3 link, etc.) or `None` for services without one.

Call these from your controllers rather than `obj.service.send_file(...)` / `obj.service.service_url(...)` directly, so disposition stays consistent across paths.


### Content disposition

When serving files, Proper Storage automatically decides whether to serve them inline or as a download based on the `STORAGE_ALLOWED_INLINE` config:

```python
STORAGE_ALLOWED_INLINE = [
    "image/*",
    "video/*",
    "application/pdf",
]
```

Content types matching any of these glob patterns (via `fnmatch`) are served inline (displayed in the browser). All other types are served as attachments (triggering a download). `Attachment.send_file()` and `Attachment.service_url()` apply this rule, so controllers don't need to think about it.


## Downloading Files

To get the raw bytes of an attachment:

```python
data = attachment.download()
```


## Removing Files

To delete an attachment and its file from storage:

```python
attachment.purge()
```

This deletes both the file from the storage service and the database record.


## Variants

Variants are transformed versions of an attachment — thumbnails, resized images, format conversions, etc. They are stored as regular Attachment records with a foreign key back to the parent, so they get the full Attachment API (upload, download, send_file, purge, url) for free.

Variants are identified by a hash of their transformations, so calling `variant()` with the same arguments is idempotent — it returns the existing variant instead of creating a duplicate. The transformations are also stored unhashed in the variant's `metadata["ops"]` for introspection.

> **Prerequisite:** Image variants require [libvips](https://www.libvips.org/install.html) to be installed on your system. On Debian/Ubuntu: `apt install libvips-dev`. On macOS: `brew install vips`. The `pyvips` Python package is also required: `uv add pyvips`.


### Using `variant()`

Call `variant(**ops)` on any saved attachment. The content type is checked and the appropriate transform method is called:

```python
thumb = attachment.variant(resize_to_fill=(400, 400))
thumb.url
```

Calling it again with the same transformations returns the existing variant:

```python
attachment.variant(resize_to_fill=(400, 400))  # returns same variant, no reprocessing
```

You can chain multiple operations. They are applied in order:

```python
attachment.variant(
    resize_to_fit=(800, 800),
    rotate=(45,),
)
```

You can inspect what transformations produced a variant via its metadata:

```python
thumb.metadata["ops"]  # {"resize_to_fill": [400, 400]}
```

If the content type is not supported, a `ValueError` is raised.


### Available transformations

#### Resize operations

All resize operations preserve the aspect ratio and apply a mild sharpening to the result. Options are forwarded to [`vips_thumbnail()`](https://www.libvips.org/API/current/ctor.Image.thumbnail.html).

**`resize_to_fit`** (alias: **`resize`**) — Resize the image to fit within the given dimensions, preserving aspect ratio. Either dimension can be `None` to constrain only the other. Will upsize if the image is smaller.

```python
attachment.variant(resize_to_fit=(400, 400))  # 600x800 => 300x400
```

**`resize_to_fill`** — Resize and crop to fill the exact dimensions. Crops from the center by default.

```python
attachment.variant(resize_to_fill=(400, 400))             # center crop
attachment.variant(resize_to_fill=(400, 400, "attention")) # smart crop
```

**`resize_and_pad`** — Resize to fit, then pad the remaining area. Pads with black by default (or transparent if the source has an alpha channel).

```python
attachment.variant(resize_and_pad=(400, 400))
attachment.variant(resize_and_pad=(400, 400, {"gravity": "north-west"}))
attachment.variant(resize_and_pad=(400, 400, {"alpha": True, "background": [255, 255, 255]}))
```

#### Orientation

**`rotate`** — Rotate by an arbitrary angle in degrees. For non-90-degree rotations, a background color fills the corners (defaults to black).

```python
attachment.variant(rotate=(90,))
attachment.variant(rotate=(45, {"background": [255, 255, 255]}))
```

**`fliphor`**, **`flipver`** — Flip horizontally or vertically, no arguments needed.

```python
attachment.variant(fliphor=())
attachment.variant(flipver=())
```

#### Color filters

**`grayscale`** — Convert to grayscale. The three optional values control how much each source channel (R, G, B) contributes to the result. Defaults to BT.601 perceptual luminance weights.

```python
attachment.variant(grayscale=())                       # standard
attachment.variant(grayscale=(0.333, 0.333, 0.334))    # equal weight
attachment.variant(grayscale=(0.0, 1.0, 0.0))          # green channel only
```

**`sepia`** — Apply a sepia tone. The three optional values are per-channel multipliers applied after converting to grayscale. Defaults produce a classic warm sepia.

```python
attachment.variant(sepia=())                   # classic sepia
attachment.variant(sepia=(1.0, 0.85, 0.6))     # warmer
attachment.variant(sepia=(0.9, 0.9, 0.8))      # subtle, cooler
```

**`blur`** — Apply a Gaussian blur. The sigma value (minimum standard deviation) is required. Options are forwarded to [`vips_gaussblur()`](https://www.libvips.org/API/current/method.Image.gaussblur.html).

```python
attachment.variant(blur=(1.5,))
attachment.variant(blur=(3.0, {"precision": "integer"}))
```

#### Compositing

**`composite`** — Blend one or more images over the current one (e.g. watermark). The overlay must be a file path.

```python
attachment.variant(composite=("watermark.png",))
attachment.variant(composite=("watermark.png", {"gravity": "south-east", "offset": [10, 10]}))
attachment.variant(composite=(["logo1.png", "logo2.png"],))
```


### `load` and `save` options

The optional `load` dict is forwarded to `pyvips.Image.new_from_file()` for controlling how the source image is loaded. By default, EXIF auto-rotation is applied (`autorot=True`); pass `autorot=False` to disable it.

```python
attachment.variant(
    resize_to_fit=(800, 800),
    load={"autorot": False},
)
```

The optional `save` dict is forwarded to `pyvips.Image.write_to_buffer()` for controlling the output format and encoding. Use the `format` key to set the output file extension; if you don't, Proper resolves a default for you (see below).

```python
attachment.variant(
    resize_to_fill=(400, 400),
    save={"format": ".webp", "Q": 80},
)

attachment.variant(
    resize_to_fit=(1200, 1200),
    save={"format": ".png", "compression": 6},
)
```

When `save["format"]` is not provided:

1. If the source content type matches `STORAGE_ALLOWED_VARIANTS` (e.g. `"image/jpeg"`, `"image/png"`, `"image/gif"`, plus anything you add), the variant uses the **source format**.
2. Otherwise, it uses `STORAGE_FALLBACK_FORMAT` (default `"png"`). This covers source types like TIFF or BMP that you don't want to expose verbatim.

The resolved format is included in the variant's `variant_key`, so two calls with the same kwargs always reach the same cached variant.

See the [pyvips documentation](https://www.libvips.org/API/current/) for the full list of loader and saver options.


### Adding support for other content types

Only `image/*` is enabled by default. The framework also ships built-in `preview_pdf` (poppler's `pdftoppm`) and `preview_video` (ffmpeg). Turning either on is a one-line dict change plus installing the system tool:

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        **app.attachment_for(BaseModel).VARIANTS_ENABLED_FOR,
        "application/pdf": "preview_pdf",
        "video/*": "preview_video",
    }
```

`preview_pdf` accepts two extra kwargs on top of the usual image ops:

- `page=1` - 1-indexed page number to render.
- `dpi=150` - render resolution. Bump to `dpi=300` for sharper output.

`preview_video` accepts one:

- `at_seconds=1.0` - timestamp of the frame to grab. Defaults to one second in (dodges the common black opening frame); pass `0` for the very first frame.

For anything else (ePubs, audio waveforms, ...), extend `VARIANTS_ENABLED_FOR` and add the corresponding method:

```python
class Attachment(app.attachment_for(BaseModel)):
    VARIANTS_ENABLED_FOR = {
        **app.attachment_for(BaseModel).VARIANTS_ENABLED_FOR,
        "application/epub+zip": "preview_epub",
    }

    def preview_epub(self, source, **ops):
        # Extract cover image, then delegate to transform_image
        image_bytes = extract_cover(source)  # your extraction logic
        return self.transform_image(image_bytes, **ops)
```

The keys are content-type glob patterns matched against the attachment's `content_type` via `fnmatch`. The values are method names called with `(source, **ops)`.

Custom transform methods can call `self.transform_image(source, **ops)` to delegate image processing (resize, format conversion, etc.) after extracting an image from their source format.


### Iterating variants

```python
for v in attachment.variants:
    print(v.variant_key, v.url)
```


### Purging variants

Purging a parent attachment automatically purges all its variants first:

```python
attachment.purge()  # removes variants, then the parent
```

You can also purge only the variants, keeping the parent:

```python
attachment.purge_variants()
```


### Low-level variant creation

For full control, use `create_variant(upload)` directly. It inherits `service_name` from the parent by default (so the variant lives in the same service and inherits its access mode):

```python
thumb = attachment.create_variant(thumbnail_data)
```

You can override any Attachment option:

```python
webp = attachment.create_variant(
    converted_file,
    content_type="image/webp",
    filename="photo.webp",
)
```


## Custom Services

To add your own storage service, subclass `proper.storage.Service` and implement the four required methods:

```python
from proper.storage import Service


class GoogleCloud(Service):
    def __init__(self, app, **config):
        self.bucket_name = config.pop("bucket")
        # Initialize your client here
        super().__init__(app, **config)

    def upload(self, upload, obj):
        # Write the file to storage
        ...

    def download(self, obj):
        # Return the file contents as bytes
        ...

    def send_file(self, obj, response, as_attachment=False):
        # Set response headers and body to serve the file
        ...

    def purge(self, obj):
        # Delete the file from storage
        ...
```

Then add a config entry where the `type` matches your class name:

```python
STORAGE_SERVICES = {
    "gcs": {
        "type": "GoogleCloud",
        "bucket": "my-bucket",
        "project": "my-project",
    },
}

STORAGE = "gcs"
```

Service instances are cached for the lifetime of the application, so initialization (connecting to APIs, etc.) only happens once per service name.
