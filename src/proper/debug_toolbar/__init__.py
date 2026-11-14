"""A debug toolbar: what each request did, shown at the bottom of its page.

Used only in development:

```python
if app.config.DEBUG:
    app.install_debug_toolbar()
```

Each request is recorded (route, timings, SQL queries, calls to the cache,
rendered views, log lines, request and response data) and kept in memory.
HTML pages get a bar with a summary and a link to the page of the request,
at `/__debug__/<request id>`. The requests without a page of their own (a
redirect, a Turbo Frame, JSON) are listed at `/__debug__`; the bar also
shows the last one the page made with Turbo, and the redirect that led to
the page.
"""
from .controller import DebugToolbarController
from .record import CacheCall, ComponentCall, LogLine, Query, Record, Render, Store
from .toolbar import URL_PREFIX, Toolbar


__all__ = (
    "URL_PREFIX",
    "CacheCall",
    "ComponentCall",
    "DebugToolbarController",
    "LogLine",
    "Query",
    "Record",
    "Render",
    "Store",
    "Toolbar",
)
