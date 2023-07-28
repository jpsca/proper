import os
from proper import is_development_env, is_testing_env, is_staging_or_production_env


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
    }
}

if is_development_env:
    STORAGE = "local"
elif is_staging_or_production_env:
    STORAGE = "amazon"
elif is_testing_env:
    STORAGE = "test"


# Image content types that can be processed without being converted to
# the fallback PNG format. If you want to use WebP or AVIF variants in
# your application you can add image/webp or image/avif to this list
STORAGE_WEB_IMAGE_CONTENT_TYPES = [
    "image/png",
    "image/jpeg",
    "image/gif",
]

# List of content types allowed to be served inline
STORAGE_ALLOWED_INLINE_CONTENT_TYPES = [
    "image/",
    "video/",
    "application/pdf",
]
