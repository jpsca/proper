title: Proper Storage
description: Proper Storage gives your app the power to handle file uploads without complications
----

# Proper Storage

Proper Storage is an installable addon that gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3 (and S3-compatible services like DigitalOcean Spaces or MinIO) and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest.

## 1. Setup

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


### 1.1 The Attachment model

The generated model uses the `app.storage.Attachment` mixin, which provides all the storage fields automatically (you don't need to add any columns yourself):

```python
import peewee as pw

from ..main import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    # You can add any extra fields here, like:
    # user = pw.ForeignKeyField(User, null=True)
    ...
```

The mixin provides these fields:

Field            | Type                   | Description
---------------- | ---------------------- | ---------------------------------
`id`             | UUIDField              | Primary key (auto-generated)
`service_name`   | CharField(64)          | Which storage service holds the file
`filename`       | CharField(255)         | Parameterized filename
`content_type`   | CharField(64)          | MIME type (auto-detected from filename)
`byte_size`      | IntegerField           | File size in bytes
`public`         | BooleanField           | Whether the file is publicly accessible
`created_at`     | DateTimeField          | Creation timestamp (UTC)
`metadata`       | JSONField              | Arbitrary metadata (nullable)
`parent`         | ForeignKeyField(self)  | Parent attachment for variants (nullable)
`variant_key`    | CharField(64)          | SHA-256 digest of the variant's transformations


### 1.2 Configuring services

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
if env == PROD:
    STORAGE = "amazon"
elif env == TEST:
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


## 2. Built-in Services


### 2.1. Disk service

Stores files on the local filesystem. Files are organized using a two-level directory sharding based on the attachment UUID: `{root}/{id[:2]}/{id[2:4]}/{filename}`.

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

The `root` path is relative to your application's root directory. The directory is created automatically if it doesn't exist.


### 2.2. S3 Service (Amazon S3 and S3-compatible APIs)

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


## 3. Attaching Files to Models

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

### 3.1. Creating attachments from uploads

In a controller, create an Attachment from the uploaded file and assign it:

```python
def create(self):
    filesto = self.request.form.get("avatar")
    attachment = Attachment(filesto)
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

### 3.2. Constructor options

All options are keyword-only:

```python
attachment = Attachment(
    filesto,
    service_name="amazon",       # override the default service
    filename="custom-name.jpg",  # override the detected filename
    content_type="image/jpeg",   # override the detected MIME type
    public=True,                 # make publicly accessible
)
```


## 4. Serving Files

The `proper install storage` command creates two controllers for serving files:


### 4.1. Private files (signed URLs)

Private files are served through signed, time-limited URLs. The `url_for` property on an attachment generates the appropriate URL:

```python
attachment.url_for
# => "/storage/aBcDe..."  (signed)
```

The signed URL is verified by the `AttachmentController`:

```python
@router.resource("storage", pk="pk")
class AttachmentController(AppController):
    def show(self):
        signed_pk = self.params.get("pk")
        obj = app.storage.get_attachment(signed_pk, max_age=None)
        if not obj:
            raise NotFound
        # Add any extra guards here, like checking if the user has access
        obj.send_file()
```

Signed URLs expire after one year by default. You can pass a custom `max_age` (in seconds) to `get_attachment()`.


### 4.2. Public files

Public files don't require signing. Set `public=True` when creating the attachment:

```python
attachment = Attachment(filesto, public=True)
attachment.save()

attachment.url_for
# => "/storage/public/550e8400-e29b-..."
```

Public files are served by the `PublicAttachmentController`, which skips authentication:

```python
@router.resource("storage/public", pk="pk")
class PublicAttachmentController(AppController):
    skip_authentication = True

    def show(self):
        pk = self.params.get("pk")
        obj = app.storage.get_public_attachment(pk)
        if not obj:
            raise NotFound
        obj.send_file()
```


### 4.3. Content disposition

When serving files, Proper Storage automatically decides whether to serve them inline or as a download based on the `STORAGE_ALLOWED_INLINE_CONTENT_TYPES` config:

```python
STORAGE_ALLOWED_INLINE_CONTENT_TYPES = [
    "image/",
    "video/",
    "application/pdf",
]
```

Content types matching any of these prefixes are served inline (displayed in the browser). All other types are served as attachments (triggering a download).


## 5. Downloading Files

To get the raw bytes of an attachment:

```python
data = attachment.download()
```


## 6. Removing Files

To delete an attachment and its file from storage:

```python
attachment.purge()
```

This deletes both the file from the storage service and the database record.


## 7. Variants

Variants are transformed versions of an attachment — thumbnails, resized images, format conversions, etc. They are stored as regular Attachment records with a foreign key back to the parent, so they get the full Attachment API (upload, download, send_file, purge, url_for) for free.

Variants are identified by a hash of their transformations, so calling `variant()` with the same arguments is idempotent — it returns the existing variant instead of creating a duplicate. The transformations are also stored unhashed in the variant's `metadata["ops"]` for introspection.

> **Prerequisite:** Image variants require [libvips](https://www.libvips.org/install.html) to be installed on your system. On Debian/Ubuntu: `apt install libvips-dev`. On macOS: `brew install vips`. The `pyvips` Python package is also required: `pip install pyvips`.


### 7.1. Using `variant()`

Call `variant(**ops)` on any saved attachment. The content type is checked and the appropriate transform method is called:

```python
thumb = attachment.variant(resize_to_fill=(400, 400))
thumb.url_for
```

Calling it again with the same transformations returns the existing variant:

```python
attachment.variant(resize_to_fill=(400, 400))  # returns same variant, no reprocessing
```

You can chain multiple operations. They are applied in order:

```python
attachment.variant(
    resize_to_limit=(800, 800),
    rotate=(45,),
)
```

You can inspect what transformations produced a variant via its metadata:

```python
thumb.metadata["ops"]  # {"resize_to_fill": [400, 400]}
```

If the content type is not supported, a `ValueError` is raised.


### 7.2. Available transformations

#### Resize operations

All resize operations preserve the aspect ratio and apply a mild sharpening to the result. Options are forwarded to [`vips_thumbnail()`](https://www.libvips.org/API/current/ctor.Image.thumbnail.html).

**`resize_to_limit`** — Shrink the image so it fits within the given dimensions. Never upsizes. Either dimension can be `None` to constrain only the other.

```python
attachment.variant(resize_to_limit=(400, 400))  # 600x800 => 300x400
attachment.variant(resize_to_limit=(400, None))  # constrain width only
```

**`resize_to_fit`** — Resize the image to fit within the given dimensions. Will upsize if the image is smaller.

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


### 7.3. `load` and `save` options

The optional `load` dict is forwarded to `pyvips.Image.new_from_file()` for controlling how the source image is loaded. By default, EXIF auto-rotation is applied (`autorot=True`); pass `autorot=False` to disable it.

```python
attachment.variant(
    resize_to_limit=(800, 800),
    load={"autorot": False},
)
```

The optional `save` dict is forwarded to `pyvips.Image.write_to_buffer()` for controlling the output format and encoding. Use the `format` key to set the output file extension (defaults to `".jpg"`).

```python
attachment.variant(
    resize_to_fill=(400, 400),
    save={"format": ".webp", "Q": 80},
)

attachment.variant(
    resize_to_limit=(1200, 1200),
    save={"format": ".png", "compression": 6},
)
```

See the [pyvips documentation](https://www.libvips.org/API/current/) for the full list of loader and saver options.


### 7.4. Adding support for other content types

Only `image/*` is supported out of the box. To create variants from other file types (videos, PDFs, ePubs, etc.), extend `SUPPORTED_VARIANT_TYPES` and add the corresponding method in your Attachment subclass:

```python
class Attachment(app.storage.Attachment, BaseModel):
    SUPPORTED_VARIANT_TYPES = {
        **app.storage.Attachment.SUPPORTED_VARIANT_TYPES,
        "application/pdf": "preview_pdf",
        "video/", "preview_video",
    }

    def preview_pdf(self, source, page=0, **ops):
        # Extract page as image, then delegate to transform_image
        image_bytes = pdf_to_image(source, page)  # your extraction logic
        return self.transform_image(image_bytes, **ops)
    
    def preview_video(self, source, **ops):
        # Extract frame as image, then delegate to transform_image
        image_bytes = extract_frame(source)  # your extraction logic
        return self.transform_image(image_bytes, **ops)

```

The keys are content-type prefixes matched against the attachment's `content_type`. The values are method names called with `(source, **ops)`.

Custom transform methods can call `self.transform_image(source, **ops)` to delegate image processing (resize, format conversion, etc.) after extracting an image from their source format.


### 7.4. Iterating variants

```python
for v in attachment.variants:
    print(v.variant_key, v.url_for)
```


### 7.5. Purging variants

Purging a parent attachment automatically purges all its variants first:

```python
attachment.purge()  # removes variants, then the parent
```

You can also purge only the variants, keeping the parent:

```python
attachment.purge_variants()
```


### 7.6. Low-level variant creation

For full control, use `create_variant(filesto)` directly. It inherits `service_name` and `public` from the parent by default:

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


## 8. Custom Services

To add your own storage service, subclass `proper.storage.Service` and implement the four required methods:

```python
from proper.storage import Service


class GoogleCloud(Service):
    def __init__(self, app, **config):
        self.bucket_name = config.pop("bucket")
        # Initialize your client here
        super().__init__(app, **config)

    def upload(self, filesto, obj):
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
