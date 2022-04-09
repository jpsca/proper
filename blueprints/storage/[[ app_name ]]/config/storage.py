from proper import Dot, is_development_env, is_testing_env, is_staging_or_production_env


config = storage_config = Dot()

local = config.local = Dot()
local.service = "disk"
local.root = "storage/"

test = config.test = Dot()
test.service = "disk"
test.root = "temp/storage"

# Replace with your real production service
amazon = config.amazon = Dot()
amazon.service = "s3"
amazon.access_key_id = ""  # IN CREDENTIALS
amazon.secret_access_key = ""  # IN CREDENTIALS
amazon.bucket = "..."
amazon.region = "..."  # e.g. 'us-east-1'

if is_development_env:
    storage_config.service = "local"
elif is_staging_or_production_env:
    storage_config.service = "amazon"
elif is_testing_env:
    storage_config.service = "test"
