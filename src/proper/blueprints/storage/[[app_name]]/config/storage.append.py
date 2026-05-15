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

    # Replace with your real production service
    "amazon": {
        "type": "S3",
        "access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "bucket": "...",
        "region": "...",  # e.g. 'us-east-1'
    },

    # An example of a public service. Files stored here get unsigned URLs
    # served by PublicAttachmentController. Use it for assets that are
    # genuinely meant to be world-readable.
    # "amazon_public": {
    #     "type": "S3",
    #     "public": True,
    #     "bucket": "...",
    #     "region": "...",
    # },
}

STORAGE = "local"
if env == "prod":
    STORAGE = "amazon"
elif env == "test":
    STORAGE = "test"


# Image content types that can be processed without being converted to
# the fallback format. If you want to use WebP or AVIF variants in
# your application you can add image/webp or image/avif to this list
STORAGE_ALLOWED_VARIANTS = [
    "image/png",
    "image/jpeg",
    "image/gif",
]
# Format used for variants when the source content type isn't in
# STORAGE_ALLOWED_VARIANTS (and the caller didn't pass save={"format": ...})
STORAGE_FALLBACK_FORMAT = "png"

# Glob patterns of content types allowed to be served inline
STORAGE_ALLOWED_INLINE = [
    "image/*",
    "video/*",
    "application/pdf",
]
