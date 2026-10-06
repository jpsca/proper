import os


CABLE_PATH = "/cable"

# Port of the WebSockets. In production, point the proxy's `CABLE_PATH`
# location at it; in development the browser connects to it directly.
CABLE_PORT = int(os.getenv("CABLE_PORT", int(os.getenv("PORT", 2300)) + 1))

# The WebSockets are served by proper-wse (Rust), from the web process that
# `proper run` starts. Broadcasts made in any other process (a task worker, a
# shell) are forwarded to it. No Redis needed on one machine.
CABLE: dict = {"type": "proper.channels.wse.WseCable"}

# Other backends:
# - The in-process cable, served by a second process over RSGI:
#     CABLE = {}
# - The same cable on several machines, through Redis (needs `uv add redis`):
#     CABLE = {
#         "type": "proper.channels.RedisCable",
#         "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
#         "prefix": "[[app_name]]:cable:",
#     }
