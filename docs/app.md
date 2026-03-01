title: Application
----

# Application

## 1. Setup

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
    base.py               # BaseModel and BaseMixin with db connection
    __init__.py           # Must import all models for migration detection
  views/                  # Jinja/Jx templates
    layouts/              # Base layouts (app.jinja, email.jinja)
    pages/                # Page templates, mirroring controller structure
    common/               # Shared partials (nav, flashes)
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

## 1.1 Main dependencies

Once installed, a Proper web app depends on some other Python libraries, most notably:

- [Peewee ORM](https://docs.peewee-orm.com/)
- [Huey](https://huey.readthedocs.io/) for background tasks
- [Jx](https://jx.scaletti.dev/) for component templates
- [Formidable](https://formidable.scaletti.dev/) for form handling

Read the documentation of these libraries to understand how to work with them in Proper.


## 2. Request Lifecycle

Every request flows through a middleware pipeline in this exact order:

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


## 3. Global Context

The `current` object provides request-scoped global access to the app, request, and response from anywhere — controllers, models, helpers, templates:

```python
from proper import current

current.app            # The App instance
current.request        # The current Request
current.response       # The current Response
```

It uses Python's `contextvars` module, so it's safe for threaded and async environments. Custom attributes can be set on it too (e.g., the auth system sets `current.user` and `current.auth_session`).


## 4. Configuration

All config lives in `myapp/config/`. The `__init__.py` imports modules in order, and later modules can override earlier values. Config is accessed as attributes:

```python
app.config.DEBUG
app.config.SECRET_KEYS
app.config.DATABASES
```

Environment is set via `APP_ENV` (values: `dev`, `test`, `prod`).

### 4.1 Core Settings (`config/main.py`)

| Setting                    | Default           | Description                                    |
|----------------------------|-------------------|------------------------------------------------|
| `DEBUG`                    | `False`           | Enable debug mode                              |
| `PROTOCOL`                 | `"http"`          | `"http"` or `"https"`                          |
| `HOST`                     | `"localhost:2300"` | Hostname with port                            |
| `SECRET_KEYS`              | (required)        | List of signing keys, oldest to newest         |
| `CATCH_ALL_ERRORS`         | `True`            | Let the app handle all exceptions              |
| `MAX_CONTENT_LENGTH`       | `8 * MB`          | Max request body size                          |
| `MAX_QUERY_SIZE`           | `1 * MB`          | Max query string size                          |
| `ASSETS_URL`               | `"/assets/"`      | URL prefix for static assets                   |
| `STATIC_X_SENDFILE_HEADER` | `""`              | Header for web server file serving             |

### 4.2 Session Settings

| Setting                    | Default   | Description                              |
|----------------------------|-----------|------------------------------------------|
| `SESSION_COOKIE_LIFETIME`  | `30 * DAYS` | Session cookie max age (seconds)       |
| `SESSION_COOKIE_DOMAIN`    | `None`    | Restrict cookie to domain                |
| `SESSION_COOKIE_PATH`      | `"/"`     | Cookie path                              |
| `SESSION_COOKIE_HTTPONLY`   | `True`    | Block JavaScript access                  |
| `SESSION_COOKIE_SAMESITE`  | `"Lax"`   | `"Lax"`, `"Strict"`, or `"None"`        |

### 4.3 Other Config Keys

Storage, queue, cache, mailer, i18n, and auth settings are documented in their respective pages.


## 5. Lifecycle Hooks

Register functions that run on every request using decorators on the app:

```python
@app.on_error()
def handle_error():
    # Runs if the request raised an exception.
    # The error is available as current.response.error
    pass

@app.on_teardown()
def cleanup():
    # ALWAYS runs at the end of a request, even if an error occurred.
    # Use for cleanup: closing connections, releasing resources.
    pass
```

Multiple handlers can be registered for each hook. They run in registration order.


## 6. Static Assets

Static files in the `assets/` directory are served via a static route registered in `router.py`. The `ASSETS_URL` config controls the URL prefix (default: `/assets/`).

### 6.1 Fingerprinting

By default, asset URLs include a hash of the file's modification time for cache busting:

```
/assets/styles/app-a1b2c3d4e5f6.css
```

Fingerprinted files are served with `Cache-Control: public, max-age=31536000, immutable` (1 year). Non-fingerprinted files use `must-revalidate`. The framework also supports conditional requests via `If-Modified-Since` and `ETag` headers.

### 6.2 X-Sendfile

In production, you can offload file serving to the web server. Set `STATIC_X_SENDFILE_HEADER` to the appropriate header for your server:

```python
# NGINX
STATIC_X_SENDFILE_HEADER = "X-Accel-Redirect"

# Lighttpd
STATIC_X_SENDFILE_HEADER = "X-Sendfile"
```

When set, Proper sends the header instead of the file body, letting the web server handle the actual transfer.


## 7. Units

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


## 8. HTTP Errors

Raise HTTP errors from controllers to return specific status codes. All errors live in `proper.errors`:

```python
from proper.errors import NotFound, Forbidden, TooManyRequests

def show(self):
    photo = Photo.get_or_none(photo_id)
    if not photo:
        raise NotFound("Photo not found")
```

### 8.1 Available Errors

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

All inherit from `HTTPError`. Each has a `status_code` property and an optional message.


## 9. Helper Types

### 9.1 DotDict

A dict subclass that allows attribute-style access. Used for `app.config`, `request.session`, and `response.session`:

```python
from proper.helpers import DotDict

d = DotDict({"name": "Alice", "settings": {"theme": "dark"}})
d.name              # "Alice"
d.settings.theme    # "dark" (nested dicts are also DotDicts)
d.missing           # KeyError
```

`update()` does deep merging — nested dicts are merged recursively rather than replaced.

### 9.2 MultiDict

A dict-like type that handles multiple values per key. Used for `request.form` and `request.query`:

```python
# Given ?color=red&color=blue
request.query.get("color")           # "blue" (last value)
request.query.getall("color")        # ["red", "blue"]
request.query.get("color", index=0)  # "red" (first value)
request.query.get("count", type=int) # type-casts the value
```


## 10. CLI

The `proper` command provides these subcommands:

```bash
proper run                          # Start dev server (Gunicorn, port 2300)
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
```

All commands accept a `--help` parameter that shows more details.

Most `db` commands accept `--db=NAME` to target a specific database (default: `main`).


## 11. Logging

The `proper` logger outputs debug information for:

- Each middleware step: `[pipeline] GET /path -> middleware_name`
- Controller callbacks: `[ControllerName.action] before: callback_name (from ConcernClass)`
- Callback halts: `[ControllerName.action] halted by before callback: callback_name`
- Template inference: `[ControllerName.action] rendering inferred template: pages/.../action.jinja`
- Errors: `[error] GET /path -> ErrorType: message`

Enable with standard Python logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
