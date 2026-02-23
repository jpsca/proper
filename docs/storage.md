title: Proper Storage
description: Overview
----

## 1. What is Proper Storage?

Proper Storage gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3 (and S3-compatible services like DigitalOcean Spaces or MinIO) and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest.


## 2. Setup

```bash
$  proper install storage
$  proper db migrate
```

This sets up configuration in your application, creates the Attachment model, the serving controllers, and the `attachment` table Proper Storage needs.

The installer creates three files:

- `models/attachment.py` — your Attachment model
- `controllers/storage_controller.py` — controllers for serving files
- `config/storage.py` — service configuration

### 2.1 The Attachment model

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

### 2.2 Configuring services

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


## 3. Built-in Services

### 3.1. Disk service

Stores files on the local filesystem. Files are organized using a two-level directory sharding based on the attachment UUID: `{root}/{id[:2]}/{id[2:4]}/{filename}`.

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

The `root` path is relative to your application's root directory. The directory is created automatically if it doesn't exist.

### 3.2. S3 Service (Amazon S3 and S3-compatible APIs)

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


## 4. Attaching Files to Models

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

### 4.1. Creating attachments from uploads

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

### 4.2. Constructor options

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


## 5. Serving Files

The `proper install storage` command creates two controllers for serving files:

### 5.1. Private files (signed URLs)

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

### 5.2. Public files

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

### 5.3. Content disposition

When serving files, Proper Storage automatically decides whether to serve them inline or as a download based on the `STORAGE_ALLOWED_INLINE_CONTENT_TYPES` config:

```python
STORAGE_ALLOWED_INLINE_CONTENT_TYPES = [
    "image/",
    "video/",
    "application/pdf",
]
```

Content types matching any of these prefixes are served inline (displayed in the browser). All other types are served as attachments (triggering a download).


## 6. Downloading Files

To get the raw bytes of an attachment:

```python
data = attachment.download()
```


## 7. Removing Files

To delete an attachment and its file from storage:

```python
attachment.purge()
```

This deletes both the file from the storage service and the database record.


## 8. Variants

Variants are transformed versions of an attachment — thumbnails, resized images, format conversions, etc. They are stored as regular Attachment records with a foreign key back to the parent, so they get the full Attachment API (upload, download, send_file, purge, url_for) for free.

Variants are identified by a hash of their transformations, so calling `variant()` with the same arguments is idempotent — it returns the existing variant instead of creating a duplicate. The transformations are also stored unhashed in the variant's `metadata["transformations"]` for introspection.

### 8.1. Using `variant()`

Call `variant(**transformations)` on any saved attachment. The content type is checked and the appropriate transform method is called:

| Content type | Method called |
|---|---|
| `image/*` | `transform_image(**transformations)` |

```python
thumb = attachment.variant(resize=(100, 100))
thumb.url_for
```

Calling it again with the same transformations returns the existing variant:

```python
attachment.variant(resize=(100, 100))  # returns same variant, no reprocessing
```

You can inspect what transformations produced a variant via its metadata:

```python
thumb.metadata["transformations"]  # {"resize": [100, 100]}
```

If the content type is not supported, a `ValueError` is raised.

### 8.2. Implementing transforms

The transform methods are intentionally left unimplemented — override them in your Attachment subclass:

```python
from io import BytesIO
from PIL import Image

from ..main import app
from .base import BaseModel


class Attachment(app.storage.Attachment, BaseModel):
    def transform_image(self, **transformations):
        data = self.download()
        img = Image.open(BytesIO(data))
        if "resize" in transformations:
            img = img.resize(transformations["resize"])
        buf = BytesIO()
        img.save(buf, format=img.format)
        buf.seek(0)
        return buf
```

Each transform method receives the keyword arguments passed to `variant()` and must return a file-like object.

### 8.3. Adding support for other content types

Only `image/*` is supported out of the box. To create variants from other file types (videos, PDFs, ePubs, etc.), extend `SUPPORTED_VARIANT_TYPES` and add the corresponding method in your Attachment subclass:

```python
class Attachment(app.storage.Attachment, BaseModel):
    SUPPORTED_VARIANT_TYPES = {
        **app.storage.Attachment.SUPPORTED_VARIANT_TYPES,
        "application/pdf": "transform_pdf",
    }

    def transform_pdf(self, source, **transformations):
        # Extract page as image, then delegate to transform_image
        page = transformations.pop("page", 0)
        image_bytes = pdf_to_image(source, page)  # your extraction logic
        return self.transform_image(image_bytes, **transformations)
```

The keys are content-type prefixes matched against the attachment's `content_type`. The values are method names called with `(source, **transformations)`.

Custom transform methods can call `self.transform_image(source, **transformations)` to delegate image processing (resize, format conversion, etc.) after extracting an image from their source format.

### 8.4. Low-level variant creation

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

### 8.5. Iterating variants

```python
for v in attachment.variants:
    print(v.variant_key, v.url_for)
```

### 8.6. Purging variants

Purging a parent attachment automatically purges all its variants first:

```python
attachment.purge()  # removes variants, then the parent
```

You can also purge only the variants, keeping the parent:

```python
attachment.purge_variants()
```


## 9. Custom Services

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
