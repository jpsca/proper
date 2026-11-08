---
title: Storage: Variants, Previews and Custom Services
description: Storage addon, second level: `variant()` transformations, load/save options, purging and eager-loading variants, previews of PDFs and videos, custom previewers, writing a storage service
last_verified: 2026-11-07
sources:
  - src/proper/storage
  - src/proper/tools/storage.py
---

# Storage: Variants, Previews and Custom Services

Builds on [storage.md](storage.md). Variants need libvips and `pyvips`; previews of PDFs and videos need poppler and ffmpeg. Each section names its tools.

## Table of Contents

- [Variants](#variants)
- [Previewing Non-Image Files](#previewing-non-image-files)
- [Custom Services](#custom-services)


## Variants

Variants are transformed versions of an attachment — thumbnails, resized images, format conversions, etc. They are stored as regular Attachment records with a foreign key back to the parent, so they get the full Attachment API (upload, download, send_file, purge, url) for free. They inherit the parent's `service_name` (and therefore its access mode) unless you override it.

Variants are identified by a SHA-256 hash of their transformations + resolved save format, stored as `variant_key`. Calling `variant()` with the same arguments is idempotent — it returns the existing variant instead of creating a duplicate. The transformations are also stored unhashed in `metadata["ops"]` for introspection.

> **Prerequisite:** Image variants require the [libvips](https://www.libvips.org/install.html) system library; the installer already adds the `pyvips` package to your dependencies. The generated `Attachment` model validates its previewers every time an instance is made, so with `"image/*"` enabled in `VARIANTS_ENABLED_FOR` even loading an attachment raises `ImportError` until libvips and pyvips are present (the same for `pdftoppm` and `ffmpeg` when their lines are enabled).

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
`resize_to_fill`  | `(w, h)`          | Fill exactly, crop the longer side. Center crop by default. Pass `(w, h, {"crop": "attention"})` for smart crop.
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

`load` is forwarded to `pyvips.Image.new_from_buffer()` (controls how the source is read; `autorot=True` is default, `autorotate` is accepted as an alias). `save` is forwarded to `pyvips.Image.write_to_buffer()`:

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

1. If the source content type matches `STORAGE_ALLOWED_VARIANTS` (see [Baseline Configuration](storage.md#baseline-configuration)), preserve the **source format**.
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
@app.queue.task()
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

`preview_video` runs ffmpeg with `-protocol_whitelist file` and `-format_whitelist` from `Attachment.VIDEO_FORMATS` (`mov` (MP4, MOV, M4V, 3GP), `matroska`, `webm`, `avi`, `mpegts`, `mpeg`, `ogg`, `flv`): an upload that is a playlist (concat, HLS) can't make ffmpeg read other files or URLs. Override `VIDEO_FORMATS` on your `Attachment` model for another format.

Preview methods accept extra kwargs that participate in the variant cache key (so different pages/timestamps cache independently):

- `preview_pdf(..., page=1, dpi=150)`
- `preview_video(..., at_seconds=1.0)`

```python
pdf_attachment.variant(resize_to_fit=(400, 400), page=2, dpi=300)
video_attachment.variant(resize_to_fit=(400, 400), at_seconds=5.0)
```

`variant()` passes the previewer's options (`page`, `dpi`, `at_seconds`) to the previewer and the transformations to the image pipeline; both are part of the variant key, so `page=2` is a different variant from `page=3`.

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

To add your own storage service, subclass `proper.storage.Service` and implement four methods (`upload`, `download`, `send_file`, `purge`); add `service_url()` if the service has a native URL (the default returns `None`) and `direct_upload_url()` if you use direct uploads. The class must be imported somewhere (the service types are found through `Service.__subclasses__()`), and a subclass named like a built-in (`S3`) replaces it:

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

Then add a config entry where the `type` matches your class name. The class may also subclass another service, such as `Disk` or `S3`:

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

[`proper/storage/services/disk.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/disk.py) and [`proper/storage/services/s3.py`](https://github.com/jpsca/proper/blob/main/src/proper/storage/services/s3.py) are short: `s3.py` covers all six methods, `disk.py` all but `service_url()`, plus their constructors.
