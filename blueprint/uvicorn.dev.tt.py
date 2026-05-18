"""Uvicorn configuration for development.

These values are passed as keyword arguments to `uvicorn.run()`.
"""

app = "[[ app_name ]].main:app"
host = "0.0.0.0"
reload = True
workers = 1
log_level = "info"
access_log = True
timeout_keep_alive = 900000
