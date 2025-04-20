title: Proper Storage
description: Overview
----

## 1. What is Proper Storage?

Proper Storage gives your app the power to handle file uploads without complications. It speaks fluently with Amazon S3, Google Cloud Storage, Microsoft Azure, and your local disk. You set a foreign key to the Attachment model, and Proper takes care of the rest: straightforward and without "duct tape".

Using Proper Storage, an application can transform image uploads or generate thumbnails even for some non-image uploads like PDFs and videos.

### 1.1. Requirements

Various features of Proper Storage depend on non-python third-party software which Proper will not install, and must be installed separately:

- [libvips v8.6+](https://github.com/libvips/libvips) for image analysis and transformations
- [ffmpeg v3.4+](http://ffmpeg.org/) for video previews and ffprobe for video/audio analysis
- [poppler](https://poppler.freedesktop.org/) for PDF previews


## 2. Setup

```bash
$  proper install storage
$  proper db migrate
```

This sets up configuration in your application, and creates the the `attachment` table Proper Storage needs.

Declare Proper Storage services in config/storage.py. For each service your application uses, provide a name and the its configuration. The example below declares three services named local, test, and amazon:

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

Then, tell Proper Storage which service to use by setting the `STORAGE` config to the name of thw service. Because each environment will likely use a different service, this is the default configuration in `config/storage.py`:

```python
STORAGE = "local"
if env == PROD:
    STORAGE = "amazon"
elif env == TEST:
    STORAGE = "test"
```

You probably want to use the `proper.env` value in the bucket names to further reduce the risk of accidentally destroying production data.

```python
STORAGE_SERVICES = {
    "amazon": {
      "type": "S3",
      # ...
      "bucket": f"your_own_bucket-{env}",
    },
    "google": {
      "type": "GCS",
      # ...
      "bucket": f"your_own_bucket-{env}",
    },
    "azure": {
      "type": "AzureStorage"
      # ...
      "container": f"your_container_name-{env}",
    },
    # ...
}
```

### 2.1 Disk service

```python
"local": {
    "type": "Disk",
    "root": "storage/",
}
```

### 2.2 S3 Service (Amazon S3 and S3-compatible APIs)

```python
"amazon": {
    "type": "S3",
    "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "bucket": f"your_own_bucket-{env}",
    "region": "...",  # e.g. 'us-east-1'
}
```

There are many other options available. You can check them in [AWS S3 Client](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html) documentation.

Add the `boto3` gelibrary to your requirements:

```bash
uv add boto3
```

<Alert type="warning">
The core features of Active Storage require the following permissions: `s3:ListBucket`, `s3:PutObject`, `s3:GetObject`, and `s3:DeleteObject`. Public access additionally requires `s3:PutObjectAcl`. If you have additional upload options configured such as setting ACLs then additional permissions may be required.
</Alert>

<Alert type="warning">
If you want to use environment variables, standard SDK configuration files, profiles, IAM instance profiles or task roles, you can omit the `access_key_id`, `secret_access_key`, and `region` keys in the example above. The S3 Service supports all of the authentication options described in the AWS SDK documentation.
</Alert>

To connect to an S3-compatible object storage API such as DigitalOcean Spaces, provide the endpoint:

```python
"digitalocean": {
    "type": "S3",
    "endpoint": "https://nyc3.digitaloceanspaces.com",
    "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
    "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    "bucket": f"your_own_bucket-{env}",
    "region": "...",  # e.g. 'us-east-1'
}
```

### 2.3. Microsoft Azure Storage Service

TBD

### 2.4. Google Cloud Storage Service

TBD

### 2.5 Mirror service

TBD

### 2.6. Public access

By default, Proper Storage assumes private access to services. This means generating signed, single-use URLs for blobs. If you'd rather make blobs publicly accessible, specify `"public": True` in the config for your service:

```python
STORAGE_SERVICES = {
  "public_s3": {
      "type": "S3",
      "endpoint": "https://nyc3.digitaloceanspaces.com",
      "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
      "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
      "bucket": f"your_own_bucket-{env}",
      "region": "...",  # e.g. 'us-east-1'
      "public": True,
  },
  "private_s3": {
      "type": "S3",
      "endpoint": "https://nyc3.digitaloceanspaces.com",
      "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
      "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
      "bucket": f"your_own_bucket-{env}",
      "region": "...",  # e.g. 'us-east-1'
  },
  # ...
}
```

## Attaching Files


## 4. Removing Files


## 5. Serving Files


## 6. Downloading Files


## 7. Analyzing Files


## 8. Rendering Files

