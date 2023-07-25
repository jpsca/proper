import os


redis = {
    "host": os.getenv("REDIS_HOST", "127.0.0.1"),
    "port": os.getenv("REDIS_PORT", 6379),
    "user": os.getenv("REDIS_USER"),
    "password": os.getenv("REDIS_PASSWORD"),
    "db": os.getenv("REDIS_DB", 0),
}
