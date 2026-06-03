---
title: Application
description: App setup, request lifecycle, configuration, lifecycle hooks, static assets, and logging
last_verified: 2026-06-03
---

# Application

## Table of Contents

- [Setup](#setup)
- [Main dependencies](#main-dependencies)
- [Request Lifecycle](#request-lifecycle)
- [Global Context](#global-context)
- [Configuration](#configuration)
- [Lifecycle Hooks](#lifecycle-hooks)
- [Static Assets](#static-assets)
- [Units](#units)
- [HTTP Errors](#http-errors)
- [Status Codes](#status-codes)
- [Helper Types](#helper-types)
- [CLI](#cli)
- [Middleware](#middleware)
- [Logging](#logging)

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
    main.py               # Core settings: DEBUG, HOST, SECRET_KEYS, MAILER
    storage.py            # DATABASES, QUEUE, CACHE config by environment
  controllers/            # Request handlers
    concerns/             # Controller mixins (e.g., SecurityHeaders)
    app_controller.py     # Base controller all others inherit from
    public_controller.py  # Default controller for index and error pages
  models/                 # Peewee ORM models
    concerns/             # Model mixins (e.g., Timestamped)
    base.py               # BaseModel with db connection
    __init__.py           # Must import all models for migration detection
  views/                  # Jx components
    layouts/              # Base layouts (app.jx, email.jx)
    emails/               # Email templates
  forms/                  # Form validation classes
  emails/                 # Email message classes
  tasks/                  # Background job definitions (Huey tasks)
  assets/                 # Static files (CSS, JS, images, fonts)
  cli/                    # Custom CLI commands
  router.py               # Route definitions
  main.py                 # App instantiation
db/                       # Database migrations
  main/                   # Migrations for the main database
storage/                  # Uploaded files and SQLite databases
tests/                    # Test suite
```

## Main dependencies

Once installed, a Proper web app depends on some other Python libraries, most notably:

- [Peewee ORM](https://docs.peewee-orm.com/)
- [Huey](https://huey.readthedocs.io/) for background tasks
- [Jx](https://jx.scaletti.dev/) for component templates
- [Formidable](https://formidable.scaletti.dev/) for form handling

Read the documentation of these libraries to understand how to work with them in Proper.


## Request Lifecycle

Proper is an ASGI application. However, the code of the web applications that use Proper (meaning, the code that you write) is
regular sync python.

The async boundary is handled by the framework: the ASGI entry point receives the request asynchronously, parses the body, then runs the sync pipeline in a thread via `asyncio.to_thread()`.

Every request flows through a pipeline in this exact order:

1. **copy_session** — reads the signed `_session` cookie into `request.session`
2. **head_to_get** — converts HEAD requests to GET (body stripped later)
3. **method_override** — converts POST to PUT/PATCH/DELETE via `_method` param or `X-HTTP-Method-Override` header
4. **match** — matches the URL to a route, sets `request.matched_route` and `request.matched_params`
5. **redirect** — if the matched route is a redirect, sends the redirect response and stops
6. **dispatch** — instantiates the controller and calls `_dispatch(action_name)`:
   - Runs **before** callbacks in MRO order
   - If any before callback sets a response body, the action is **skipped silently**
   - Calls the action method
   - Runs **after** callbacks in reverse MRO order
7. **strip_body_if_head** — removes body for original HEAD requests
8. **update_session_cookie** — writes back modified session as a signed cookie

The framework also manages database connections around the pipeline: it opens connections before step 1 and closes them after step 8. If an unhandled error occurs, a rollback is issued before closing.

All steps are logged at DEBUG level with the `proper` logger (prefix `[pipeline]`).


## Global Context

The `current` object provides request-scoped global access to the app, request, and response from anywhere — controllers, models, helpers, templates:

```python
from proper import current

current.app            # The App instance
current.request        # The current Request
current.response       # The current Response
```

It uses Python's `contextvars` module, so it's safe for threaded and async environments. Custom attributes can be set on it too. The following attributes are set by the framework and its built-in tools:

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
| `PORT`                     | `2300`            | Port the dev server binds to (used by `app_cli`) |
| `SECRET_KEYS`              | (required)        | List of signing keys, oldest to newest         |
| `CATCH_ALL_ERRORS`         | `True`            | Let the app handle all exceptions              |
| `MAX_CONTENT_LENGTH`       | `8 * MB`          | Max request body size                          |
| `MAX_QUERY_SIZE`           | `1 * MB`          | Max query string size                          |
| `MAX_FORM_FILES`           | `10`              | Max number of files in a multipart form        |
| `MAX_FORM_FIELDS`          | `100`             | Max number of fields in a multipart form       |
| `MAX_FORM_PART_SIZE`       | `2 * MB`          | Max size of each part in a multipart form      |
| `LOCALE_DEFAULT`           | `"en"`            | Fallback locale when none is set on the request |
| `TIMEZONE_DEFAULT`         | `"UTC"`           | Fallback timezone when none is set on the request |
| `ASSETS_URL`               | `"/assets/"`      | URL prefix for static assets                   |
| `STATIC_X_SENDFILE_HEADER` | `""`              | Header for web server file serving             |

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
| `TEMPLATE_EXTENSIONS`      | `[]`      | Extra Jinja2 extensions to load into the catalog         |
| `IMPORT_MAP`               | `{}`      | JavaScript import map (`{"@hotwired/stimulus": "path"}`) |
| `TRUSTED_ORIGINS`          | `[]`      | Origins allowed by `OriginProtection` (e.g. `["https://example.com"]`) |

### Other Config Keys

Storage, queue, cache, mailer, i18n, and auth settings are documented in their respective pages.


## Lifecycle Hooks

Register functions that run on every request using decorators on the app:

```python
@app.on_error
def handle_error():
    # Runs if the request raised an exception.
    # The error is available as current.response.error
    pass

@app.on_teardown
def cleanup():
    # ALWAYS runs at the end of a request, even if an error occurred.
    # Use for cleanup: closing connections, releasing resources.
    pass
```

Multiple handlers can be registered for each hook. They run in registration order.


## Signed Serialization

The app provides `dumps()` and `loads()` for signed, URL-safe serialization using the app's secret keys. Used internally by token generation (`ProperModel.generate_token`) and available for custom use:

```python
# Sign and serialize a value
token = app.dumps({"user_id": 42}, salt="invite")

# Deserialize and verify (tries all secret keys in order)
data = app.loads(token, max_age=3600, salt="invite")  # Returns None if expired/invalid
```

`dumps()` always uses the first (newest) secret key. `loads()` tries all keys, allowing key rotation without invalidating existing tokens.


## Attachment Model Factory

The storage addon's generated `models/attachment.py` calls `app.attachment_for(BaseModel)` to build an `Attachment` subclass bound to the app's database and storage services:

```python
# models/attachment.py
from .base import BaseModel

class Attachment(app.attachment_for(BaseModel)):
    pass
```

`attachment_for()` is memoized per `(app, base_model_cls)`, so importing the module repeatedly returns the same class — avoiding duplicate Peewee model definitions for the same `attachment` table. See [storage.md](storage.md) for the full lifecycle.


## Static Assets

Static files in the `assets/` directory are served via a static route registered in `router.py`. The `ASSETS_URL` config controls the URL prefix (default: `/assets/`).

### Fingerprinting

By default, asset URLs include a hash of the file's modification time for cache busting:

```
/assets/css/app-a1b2c3d4e5f6.css
```

Fingerprinted files are served with `Cache-Control: public, max-age=31536000, immutable` (1 year). Non-fingerprinted files use `must-revalidate`. The framework also supports conditional requests via `If-Modified-Since` and `ETag` headers.

### X-Sendfile

In production, you can offload file serving to the web server. Set `STATIC_X_SENDFILE_HEADER` to the appropriate header for your server:

```python
# NGINX
STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"

# Lighttpd
STATIC_X_SENDFILE_HEADER = "X-Sendfile"
```

When set, Proper sends the header instead of the file body, letting the web server handle the actual transfer.


## Units

Proper provides readable constants for sizes and durations, used throughout configuration:

```python
from proper.units import MB, GB, SECONDS, MINUTES, HOURS, DAYS, WEEKS
```

**Size:**

| Constant | Value   |
|----------|---------|
| `B`      | 1       |
| `KB`     | 1024    |
| `MB`     | 1048576 |
| `GB`     | 2^30    |
| `TB`     | 2^40    |

**Time** (in seconds):

| Constant           | Value     |
|--------------------|-----------|
| `SECOND` / `SECONDS` | 1      |
| `MINUTE` / `MINUTES` | 60     |
| `HOUR` / `HOURS`     | 3600   |
| `DAY` / `DAYS`       | 86400  |
| `WEEK` / `WEEKS`     | 604800 |
| `MONTH` / `MONTHS`   | 2592000 (30 days) |
| `YEAR` / `YEARS`     | 31536000 (365 days) |

There's also `to_seconds(**kwargs)` which converts `timedelta` keyword arguments:

```python
from proper.units import to_seconds

to_seconds(hours=2, minutes=30)  # 9000
```


## HTTP Errors

Raise HTTP errors from controllers to return specific status codes. All errors live in `proper.errors`:

```python
from proper.errors import NotFound, Forbidden, TooManyRequests

def show(self):
    photo = Photo.get_or_none(photo_id)
    if not photo:
        raise NotFound("Photo not found")
```

### Available Errors

| Status | Class                      | Notes                                |
|--------|----------------------------|--------------------------------------|
| 400    | `BadRequest`               |                                      |
| 401    | `Unauthorized`             |                                      |
| 403    | `Forbidden`                |                                      |
| 403    | `InvalidOrigin`            | Origin protection failure            |
| 404    | `NotFound`                 |                                      |
| 405    | `MethodNotAllowed`         | Sets `Allow` header automatically    |
| 406    | `NotAcceptable`            |                                      |
| 409    | `Conflict`                 |                                      |
| 410    | `Gone`                     |                                      |
| 413    | `RequestEntityTooLarge`    | Body exceeds `MAX_CONTENT_LENGTH`    |
| 414    | `UriTooLong`               | Query exceeds `MAX_QUERY_SIZE`       |
| 415    | `UnsupportedMediaType`     |                                      |
| 422    | `UnprocessableEntity`      |                                      |
| 429    | `TooManyRequests`          | Rate limit exceeded                  |
| 451    | `UnavailableForLegalReasons` |                                    |
| 500    | `InternalServerError`      | Aliases: `ServerError`, `Error`      |

All inherit from `HTTPError`. Each has a `status` attribute and an optional message.


## Status Codes

Import as `from proper import status` or `from proper.status import ok, not_found, ...`.

### Informational (1xx)

| Constant                | Value |
|-------------------------|-------|
| `http_continue`         | 100   |
| `switching_protocols`   | 101   |
| `processing`            | 102   |

### Successful (2xx)

| Constant                          | Value |
|-----------------------------------|-------|
| `ok`                              | 200   |
| `created`                         | 201   |
| `accepted`                        | 202   |
| `non_authoritative_information`   | 203   |
| `no_content`                      | 204   |
| `reset_content`                   | 205   |
| `partial_content`                 | 206   |
| `multi_status`                    | 207   |
| `already_reported`                | 208   |
| `im_used`                         | 226   |

### Redirection (3xx)

| Constant               | Value |
|------------------------|-------|
| `multiple_choices`     | 300   |
| `moved_permanently`    | 301   |
| `found`                | 302   |
| `see_other`            | 303   |
| `not_modified`         | 304   |
| `use_proxy`            | 305   |
| `temporary_redirect`   | 307   |
| `permanent_redirect`   | 308   |

### Client Error (4xx)

| Constant                           | Value |
|------------------------------------|-------|
| `bad_request`                      | 400   |
| `unauthorized`                     | 401   |
| `payment_required`                 | 402   |
| `forbidden`                        | 403   |
| `not_found`                        | 404   |
| `method_not_allowed`               | 405   |
| `not_acceptable`                   | 406   |
| `proxy_authentication_required`    | 407   |
| `request_timeout`                  | 408   |
| `conflict`                         | 409   |
| `gone`                             | 410   |
| `length_required`                  | 411   |
| `precondition_failed`              | 412   |
| `request_entity_too_large`         | 413   |
| `request_uri_too_long`             | 414   |
| `unsupported_media_type`           | 415   |
| `range_not_satisfiable`            | 416   |
| `expectation_failed`               | 417   |
| `im_a_teapot`                      | 418   |
| `unprocessable` / `unprocessable_entity` | 422 |
| `locked`                           | 423   |
| `failed_dependency`                | 424   |
| `upgrade_required`                 | 426   |
| `precondition_required`            | 428   |
| `too_many_requests`                | 429   |
| `request_header_fields_too_large`  | 431   |
| `unavailable_for_legal_reasons`    | 451   |

### Server Error (5xx)

| Constant                           | Value |
|------------------------------------|-------|
| `internal_server_error` / `server_error` | 500 |
| `not_implemented`                  | 501   |
| `bad_gateway`                      | 502   |
| `service_unavailable`              | 503   |
| `gateway_timeout`                  | 504   |
| `http_version_not_supported`       | 505   |
| `insufficient_storage`             | 507   |
| `loop_detected`                    | 508   |
| `network_authentication_required`  | 511   |

### Unofficial (7xx)

| Constant               | Value |
|------------------------|-------|
| `meh`                  | 701   |
| `inconceivable`        | 720   |
| `works_on_my_machine`  | 725   |
| `a_feature_not_a_bug`  | 726   |
| `computer_says_no`     | 740   |
| `under_caffeinated`    | 763   |


## Helper Types

### DotDict

A dict subclass that allows attribute-style access. Used for `app.config`, `request.session`, and `response.session`:

```python
from proper.helpers import DotDict

d = DotDict({"name": "Alice", "settings": {"theme": "dark"}})
d.name              # "Alice"
d.settings.theme    # "dark" (nested dicts are also DotDicts)
d.missing           # KeyError
```

`update()` does deep merging — nested dicts are merged recursively rather than replaced.

### MultiDict

A dict-like type that handles multiple values per key. Used for `request.form` and `request.query`:

```python
# Given ?color=red&color=blue
request.query.get("color")           # "blue" (last value)
request.query.getall("color")        # ["red", "blue"]
request.query.get("color", index=0)  # "red" (first value)
request.query.get("count", type=int) # type-casts the value
```


## CLI

The `proper` command provides these subcommands:

```bash
proper run                          # Start dev server (Uvicorn, port 2300)
proper routes                       # Display all registered routes

proper g resource Photo title:str   # Generate model + controller + form + views
proper g model Photo title:str      # Generate model only

proper db create "description"      # Create a migration from model changes
proper db migrate                   # Run all pending migrations
proper db migrate_to TARGET         # Run migrations up to TARGET
proper db rollback                  # Rollback the latest migration
proper db merge "name"              # Merge migrations into one
proper db todo                      # Show pending migrations
proper db done                      # Show applied migrations

proper install auth                 # Install authentication system
proper install i18n                 # Install internationalization
proper install storage              # Install file storage
proper install channels             # Install channels addon
```

All commands accept a `--help` parameter that shows more details.

Most `db` commands accept `--db=NAME` to target a specific database (default: `main`).


## Middleware

The `App` constructor accepts an optional `middleware` parameter — a sequence of ASGI middleware. Each middleware is a callable that takes an ASGI app and returns a new ASGI app. Middleware wraps the entire request/response cycle, including WebSocket handling.

```python
from myapp.config import Config

app = App("myapp", Config, middleware=[
    SentryMiddleware,
    CORSMiddleware,
])
```

Middleware is applied in reverse order (last in the list is the innermost), matching the standard ASGI convention. A middleware callable looks like:

```python
class TimingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        start = time.monotonic()
        await self.app(scope, receive, send)
        elapsed = time.monotonic() - start
        print(f"{scope['path']} took {elapsed:.3f}s")
```

Middleware runs outside of the framework's pipeline, so it does not have access to `current`, database connections, or other per-request state managed by Proper.


## Logging

The `proper` logger outputs debug information for:

- Each pipeline step: `[pipeline] GET /path -> step_name`
- Controller callbacks: `[ControllerName.action] before: callback_name (from ConcernClass)`
- Callback halts: `[ControllerName.action] halted by before callback: callback_name`
- Template inference: `[ControllerName.action] rendering inferred template: views/.../action.jx`
- Errors: `[error] GET /path -> ErrorType: message`

Enable with standard Python logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
