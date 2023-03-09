import os
from proper import DotDict, is_development_env, is_testing_env, is_staging_or_production_env


storage_config = DotDict()

local = DotDict()
local.type = "Disk"
local.root = "storage/"
storage_config.local = local

test = DotDict()
test.type = "Disk"
test.root = "temp/storage"
storage_config.test = test

# Replace with your real production service
amazon = DotDict()
amazon.type = "S3"
amazon.access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
amazon.secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
amazon.bucket = "..."
amazon.region = "..."  # e.g. 'us-east-1'
storage_config.amazon = amazon

if is_development_env:
    storage_config.service = "local"
elif is_staging_or_production_env:
    storage_config.service = "amazon"
elif is_testing_env:
    storage_config.service = "test"


# Image content types that can be processed without being converted to
# the fallback PNG format. If you want to use WebP or AVIF variants in
# your application you can add image/webp or image/avif to this list
storage_config.web_image_content_types = [
    "image/png",
    "image/jpeg",
    "image/gif",
]

# List of content types allowed to be served inline
storage_config.allowed_inline_content_types = [
    "image/",
    "video/",
    "application/pdf",
]
