import os


CABLE_PATH = "/cable"

# Port of the WebSockets. In production, point the proxy's `CABLE_PATH`
# location at it; in development the browser connects to it directly.
CABLE_PORT = int(os.getenv("CABLE_PORT", int(os.getenv("PORT", 2300)) + 1))

# The WebSockets are served by proper-wse (Rust), from the web process that
# `proper run` starts. Broadcasts made in any other process (a task worker, a
# shell) are forwarded to it.
CABLE: dict = {"type": "proper.channels.Cable"}
