import os

env = os.getenv("APP_ENV", "dev")

CABLE_PATH = "/cable"
CHANNELS: dict = {}

if env == "prod":
    CHANNELS = {
        "type": "proper.channels.RedisCable",
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "prefix": "[[app_name]]:cable:",
    }
