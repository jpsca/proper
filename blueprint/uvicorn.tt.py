"""Uvicorn configuration for production.

These values are passed as keyword arguments to `uvicorn.run()`.
"""

app = "[[app_name]].main:app"
workers = 1
log_level = "info"
access_log = True
timeout_keep_alive = 30
