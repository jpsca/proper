---
title: Application
description: App layout, request lifecycle, the `current` context, configuration, lifecycle hooks, static assets, debug error pages
last_verified: 2026-11-13
sources:
  - src/proper/app.py
  - src/proper/core
  - src/proper/global_context.py
  - src/proper/controller/static_files_controller.py
  - blueprint/[[app_name]]/config
---

# Application

How a Proper app is laid out, how a request flows through it, and the settings in `config/`. Running, checking and logging the app are in [cli.md](cli.md).

## Table of Contents

- [Setup](#setup)
- [Main dependencies](#main-dependencies)
- [Request Lifecycle](#request-lifecycle)
- [Global Context](#global-context)
- [Configuration](#configuration)
- [Lifecycle Hooks](#lifecycle-hooks)
- [Static Assets](#static-assets)
- [The Debug Error Pages](#the-debug-error-pages)


## Setup

To get started, you need to have `uv` installed.
[Follow these instructions](https://docs.astral.sh/uv/getting-started/installation/) if `uv` and `uvx` are not present in your system.

To create a new application, run:

```bash
uvx proper_new myapp
```

This generates the full project structure:

```
myapp/                    # Application package
  config/                 # Configuration modules
    __init__.py           # Imports all config modules in order
    main.py               # Core settings: DEBUG, HOST, SECRET_KEYS, MAILERS
    import_map.py         # IMPORT_MAP
    session.py            # SESSION_COOKIE_* settings
    storage.py            # DATABASES, QUEUE, CACHE config by environment
  controllers/            # Request handlers
    concerns/             # Controller mixins (e.g., SecurityHeaders)
    app_controller.py     # Base controller all others inherit from
    public_controller.py  # Default controller for index and error pages
  models/                 # Peewee ORM models
    concerns/             # Model mixins (e.g., RussianDollCached)
    base.py               # BaseModel with db connection
    __init__.py           # Must import all models for migration detection
  views/                  # Jx components
    layouts/              # Base layouts (base.jx, app.jx, email.jx)
    public/               # index.jx, error.jx, not_found.jx
    emails/               # Email templates
  forms/                  # Form validation classes
  emails/                 # Email message classes
  tasks/                  # Background job definitions (Huey tasks)
  cli/                    # Custom CLI commands
  router.py               # Route definitions
  main.py                 # App instantiation
db/                       # Database migrations
  main/                   # Migrations for the main database
assets/                   # Static files (CSS, JS, images, fonts)
storage/                  # Uploaded files and SQLite databases
tests/                    # Test suite
deploy/nginx.conf         # Reverse proxy config (see deployment.md)
log/                      # Log files
workers.py                # Huey consumer entry point
Dockerfile, compose.yml   # Container build and services
.env.example              # Environment variables to copy to .env
```


## Main dependencies

Once installed, a Proper web app depends on some other Python libraries, most notably:

- [Peewee ORM](https://docs.peewee-orm.com/)
- [Huey](https://huey.readthedocs.io/) for background tasks
- Jx components for templates, compiled to Python by Proper (`proper.views`)
- [Formidable](https://formidable.scaletti.dev/) for form handling

Read the documentation of these libraries to understand how to work with them in Proper.


## Request Lifecycle

Proper serves on free-threaded Python (a `3.14t` build) with Bearings (Linux only: WSL on Windows, a container on macOS), and the code of the web applications that use Proper (meaning, the code that you write) is regular sync Python: controllers, models, channels, tasks.

`proper run` serves the app with Bearings' raw interface: Bearings runs each request on a thread of its worker pool, calling `app._bearings(head, input, listener)`, which builds the `Request` from the head Bearings parsed. Any other server uses the app as a WSGI app (`app(environ, start_response)`), with the same pipeline. No event loop, no hand-off. The WebSockets of an app with channels are served by its cable (`Cable`), from the web process, on `CABLE_PORT` (see the channels doc).

`MAX_THREADS` is per process: the threads of Bearings' worker pool. `WORKERS` are its event loops, which never run Python. It is how many requests the app works on at once, and, since each thread opens its own database connection, how many connections it can hold. Past that, requests queue.

Every request flows through a pipeline in this exact order:

1. **head_to_get** — converts HEAD requests to GET; the body is dropped when the response is prepared
2. **method_override** — converts POST to PUT/PATCH/DELETE/QUERY via `_method` param or `X-HTTP-Method-Override` header
3. **match** — matches the URL to a route, sets `request.matched_route` and `request.matched_params`
4. **redirect** — if the matched route is a redirect, sends the redirect response and stops
5. **copy_session** — reads the signed `_session` cookie into `request.session`, when there is one
6. **dispatch** — instantiates the controller and calls `_dispatch(action_name)`:
   - Runs **before** callbacks from the base class down (reverse MRO)
   - If any before callback sets a response body, the action is **skipped silently**
   - Calls the action method
   - Runs **after** callbacks from the subclass up (MRO order)
7. **update_session_cookie** — writes back a modified session as a signed cookie

For a database configured with `"autoconnect": False`, the framework opens its connection before step 1 and closes it after step 7 (with `autoconnect`, Peewee's default, Peewee connects on the first query). A rollback is issued before closing only when a hook or the error handler itself raises, or `CATCH_ALL_ERRORS` is off and no error handler takes the error (outside `DEBUG`).

With `LOG_LEVEL = "debug"`, every step is logged by the `proper` logger (prefix `[pipeline]`).


## Global Context

The `current` object provides request-scoped global access to the app, request, and response from anywhere — controllers, models, helpers, templates:

```python
from proper import current

current.app            # The App instance
current.request        # The current Request
current.response       # The current Response
```

It uses Python's `contextvars` module, so it's safe for threaded and async environments. The whole request runs on one thread, in a context of its own, so what one request sets on `current` doesn't reach the next one on that thread. Custom attributes can be set on it too. The following attributes are set by the framework and its built-in tools:

| Attribute              | Set by          | Description                                      |
|------------------------|-----------------|--------------------------------------------------|
| `current.app`          | Framework       | The `App` instance                               |
| `current.request`      | Framework       | The current `Request`                            |
| `current.response`     | Framework       | The current `Response`                           |
| `current.user`         | Auth system     | The authenticated user model, or `None`          |
| `current.auth_session` | Auth system     | The current auth session model, or `None`        |
| `current.locale`       | I18n system     | The resolved locale string (e.g. `"en"`), or `None` |
| `current.timezone`     | I18n system     | The resolved timezone string (e.g. `"UTC"`), or `None` |

The `user`, `auth_session`, `locale`, and `timezone` attributes always return `None` (rather than raising `AttributeError`) even if their respective systems are not installed.


## Configuration

All config lives in `myapp/config/`. The `__init__.py` imports modules in order, and later modules can override earlier values. Config is accessed as attributes:

```python
app.config.DEBUG
app.config.SECRET_KEYS
app.config.DATABASES
```

Environment is set via `APP_ENV` (values: `dev`, `test`, `prod`).

### Core Settings (`config/main.py`)

| Setting                    | Default           | Description                                    |
|----------------------------|-------------------|------------------------------------------------|
| `DEBUG`                    | `False`           | Enable debug mode                              |
| `PROTOCOL`                 | `"http"`          | `"http"` or `"https"`                          |
| `HOST`                     | `"localhost:2300"` | Hostname with port                            |
| `PORT`                     | `2300`            | Port `proper run` binds to |
| `SECRET_KEYS`              | (required)        | List of signing keys, oldest to newest, each of 48 or more characters |
| `CATCH_ALL_ERRORS`         | `True`            | Let the app handle all exceptions              |
| `MAX_THREADS`              | `0`               | Threads that run your code, i.e. requests handled at once (`0` = `min(32, cpus + 4)`) |
| `WORKERS`                  | `1`               | Bearings event loops per process (network I/O, no Python); the app runs on one pool of `MAX_THREADS` threads shared by them |
| `PROCESSES`                | `1`               | Copies of the web server on the same port; try `2` with four or more cores |
| `CABLE_PORT`               | `0`               | Port where the cable (`Cable`) serves the WebSockets (`0` = none) |
| `ALLOW_GIL`                | `False`           | Let `proper run` serve on a Python with the GIL; it refuses otherwise |
| `APP_TARGET`               | `""`              | `"package.module:variable"` the server loads; empty = `app` in the module that created it |
| `RELOAD`                   | `None`            | Restart on code changes; `None` follows `DEBUG` |
| `COMPILED_PATH`            | `"_compiled"`     | Where the views are compiled, relative to the app's parent folder |
| `MAX_CONTENT_LENGTH`       | `8 * MB`          | Max request body size                          |
| `MAX_QUERY_SIZE`           | `1 * MB`          | Max query string size                          |
| `MAX_FORM_FILES`           | `10`              | Max number of files in a multipart form        |
| `MAX_FORM_FIELDS`          | `100`             | Max number of fields in a multipart or urlencoded form (a 400 past it) |
| `MAX_FORM_PART_SIZE`       | `2 * MB`          | Max size of each field that isn't a file, in a multipart form |
| `LOCALE_DEFAULT`           | `"en"`            | Fallback locale when none is set on the request |
| `TIMEZONE_DEFAULT`         | `"UTC"`           | Fallback timezone when none is set on the request |
| `ASSETS_URL`               | `"/assets/"`      | URL prefix for static assets; a full URL (`https://cdn.example.com/assets/`) makes `url_for("assets")` point at that host while the app still serves the path |
| `STATIC_X_SENDFILE_HEADER` | `""`              | Header for web server file serving             |
| `LOG_FORMAT`               | `None`            | How the root logger's handler writes every logger's records to stderr: `"console"`, `"json"` (one object per line, tracebacks without frame variables), or `"off"` (no handler). `None` = `"console"` with `DEBUG`, `"json"` without; anything else = `ConfigError` |
| `LOG_LEVEL`                | `"info"`       | Level of the `proper` logger (`proper.helpers.logger`): `"debug"`, `"info"`, `"warning"`, `"error"`, or `"critical"`; anything else = `ConfigError`. Doesn't follow `DEBUG`. Other loggers keep their own levels |
| `TRUSTED_PROXIES`          | loopback, private and link-local networks | IPs/CIDRs of the reverse proxies whose `X-Forwarded-For`, `Forwarded`, `X-Real-IP` and `X-Forwarded-Proto` are used; list every proxy in the chain (a CDN too); replaces the default; not a list of IPs/networks (strings or `ipaddress` objects) = `ConfigError`. The default also trusts any client on those networks: it can set `remote_ip` and `X-Forwarded-Proto`. A peer without an address (`proper run` or gunicorn on a Unix socket) counts as trusted |

### Session Settings

| Setting                    | Default   | Description                              |
|----------------------------|-----------|------------------------------------------|
| `SESSION_COOKIE_LIFETIME`  | `30 * DAYS` | Session cookie max age (seconds)       |
| `SESSION_COOKIE_DOMAIN`    | `None`    | Restrict cookie to domain                |
| `SESSION_COOKIE_PATH`      | `"/"`     | Cookie path                              |
| `SESSION_COOKIE_HTTPONLY`   | `True`    | Block JavaScript access                  |
| `SESSION_COOKIE_SAMESITE`  | `"Lax"`   | `"Lax"`, `"Strict"`, or `"None"`        |

### Template & Security Settings

| Setting                    | Default   | Description                                              |
|----------------------------|-----------|----------------------------------------------------------|
| `TEMPLATE_TAGS`            | `{}`      | Custom block tags for the views, `{"name": function}`    |
| `IMPORT_MAP`               | `{"@hotwired/stimulus": "js/vendor/stimulus.js", "@hotwired/turbo": "js/vendor/turbo.js"}` | JavaScript import map; the generated `config/import_map.py` sets the same |
| `TRUSTED_ORIGINS`          | `[]`      | Origins allowed by `OriginProtection` (e.g. `["https://example.com"]`) |

### Other Config Keys

Storage, queue, cache, mailer, i18n, auth, and channels (`CABLE_*`) settings are documented in their respective pages.


Signed serialization with the secret keys (`app.dumps()` / `app.loads()`) is in [security.md](security.md#signing-and-serialization). The storage addon's `app.attachment_for()` is in [storage.md](storage.md#the-attachment-model).


## Lifecycle Hooks

Register functions that run on every request using decorators on the app:

```python
@app.on_error
def handle_error():
    # Runs if the request raised an exception, before the error handlers.
    # The error is current.response.error
    pass

@app.on_teardown
def cleanup():
    # ALWAYS runs at the end of a request, even if an error occurred.
    # Use for cleanup: closing connections, releasing resources.
    pass
```

Multiple handlers can be registered for each hook. They run in registration order.

To do something before *and* after every request, use `around_request`. The function gets the request, the response, and `call_next`, and must return the response:

```python
@app.around_request
def timer(request, response, call_next):
    start = time.perf_counter()
    response = call_next(request, response)
    logger.info("%s took %.3fs", request.path, time.perf_counter() - start)
    return response
```

If the request failed, `response.error` has the exception, even when the app already showed an error page. The first function registered is the outermost one. Monitoring integrations like `proper-sentry` use this hook.


## Static Assets

Static files in the `assets/` folder at the project root (next to `storage/`, not inside the app package) are served via a static route registered in `router.py`. The `ASSETS_URL` config controls the URL prefix (default: `/assets/`).

### Fingerprinting

By default, asset URLs include a hash of the file's modification time for cache busting:

```
/assets/css/app-<64 hex characters>.css
```

Fingerprinted files are served with `Cache-Control: max-age=31536000, public, immutable` (1 year). Non-fingerprinted files use `max-age=0, public, must-revalidate`. All of them answer `If-Modified-Since` with `304 Not Modified` when the file's modification time, in whole seconds, is not newer.

### X-Sendfile

In production, you can offload file serving to the web server. Set `STATIC_X_SENDFILE_HEADER` to the appropriate header for your server:

```python
# NGINX
STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"

# Lighttpd
STATIC_X_SENDFILE_HEADER = "X-Sendfile"
```

When set, Proper sends the header instead of the file body, letting the web server handle the actual transfer.


## The Debug Error Pages

With `DEBUG`, any error (the `router.error` handlers don't run), or a route that doesn't match, is answered with a debug page, in the format the client asks for first in its `accept` header:

- `text/html` (a browser): an HTML page.
- `application/json` (or `+json`): a JSON object.
- Anything else, like `curl` or an agent (`*/*`): plain text.

To see the error of a page you are building, request it with `curl -s URL` and read the text.
