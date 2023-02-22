from proper import DotDict, is_development_env, is_testing_env, is_staging_or_production_env


storage_config = DotDict()

local = DotDict()
local.service = "disk"
local.root = "storage/"
storage_config.local = local

test = DotDict()
test.service = "disk"
test.root = "temp/storage"
storage_config.test = test

# Replace with your real production service
amazon = DotDict()
amazon.service = "s3"
amazon.access_key_id = ""  # IN CREDENTIALS
amazon.secret_access_key = ""  # IN CREDENTIALS
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
storage_config.web_image_content_types = ["image/png", "image/jpeg", "image/gif"]

# List of content types that will always serve as an attachment,
# rather than inline
storage_config.serve_as_binary_content_types = [
    "text/html",
    "image/svg+xml",
    "application/postscript",
    "application/x-shockwave-flash",
    "text/xml",
    "application/xml",
    "application/xhtml+xml",
    "application/mathml+xml",
    "text/cache-manifest",
]

# List of content types allowed to be served inline
storage_config.allowed_inline_content_types = [
    "image/png",
    "image/gif",
    "image/jpeg",
    "image/tiff",
    "image/vnd.adobe.photoshop",
    "image/vnd.microsoft.icon application/pdf",
]
