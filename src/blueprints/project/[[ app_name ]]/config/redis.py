import os

from proper import DotDict


redis_config = DotDict()
redis_config.host = os.getenv("REDIS_HOST", "localhost")
redis_config.port = os.getenv("REDIS_PORT", 6379)
redis_config.user = os.getenv("REDIS_USER")
redis_config.password = os.getenv("REDIS_PASSWORD")
redis_config.db = os.getenv("REDIS_DB", 0)
