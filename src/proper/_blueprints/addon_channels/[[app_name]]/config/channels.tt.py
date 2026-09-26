import os


env = os.getenv("APP_ENV", "dev")

CABLE_PATH = "/cable"

# `proper run` serves the WebSockets from a second process on this port.
# In production, point the proxy's `CABLE_PATH` location at it.
CABLE_PORT = int(os.getenv("CABLE_PORT", int(os.getenv("PORT", 2300)) + 1))

CABLE: dict = {}

if env == "prod":
    CABLE = {
        "type": "proper.channels.RedisCable",
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        "prefix": "[[app_name]]:cable:",
    }
