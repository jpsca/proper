# Proper Framework Conventions

This file documents the conventions, implicit behaviors, and architecture of a
Proper application. Use it as a reference when reviewing or generating code.

## Main dependencies

- [Peewee ORM](https://docs.peewee-orm.com/)
- [Huey](https://huey.readthedocs.io/)

## Project Structure

```
myapp/                    # Application package (named after your app)
  config/                 # Configuration modules (main, session, storage)
    __init__.py           # Imports all config modules in order
    main.py               # Core settings: DEBUG, HOST, SECRET_KEYS, MAILER
    session.py            # Session cookie settings
    storage.py            # DATABASES, QUEUE, CACHE config by environment
  controllers/            # Request handlers
    concerns/             # Controller mixins (e.g., SecurityHeaders)
    app_controller.py     # Base controller all others inherit from
    public_controller.py  # Default controller for index and error pages
  models/                 # Peewee ORM models
    concerns/             # Model mixins (e.g., Timestamped)
    base.py               # BaseModel and BaseMixin with db connection
    __init__.py           # Must import all models for migration detection
  views/                  # Jinja templates (Jx / .jinja files)
    layouts/              # Base layouts (app.jinja, email.jinja)
    pages/                # Page templates, mirroring controller structure
    common/               # Shared partials (nav, flashes)
    emails/               # Email templates
  forms/                  # Form validation classes
  emails/                 # Email message classes
  tasks/                  # Background job definitions (Huey tasks)
  assets/                 # Static files (CSS, JS, images, fonts)
  cli/                    # CLI commands
  router.py               # Route definitions (static assets, redirects)
  main.py                 # App instantiation: app = App(__name__, config)
db/                       # Database migrations
  main/                   # Migrations for the main database
storage/                  # Uploaded files and SQLite databases
tests/                    # Test suite
```

## Request Lifecycle

Every request flows through a middleware pipeline in this exact order:

1. **copy_session** — Reads the signed session cookie into `request.session`
2. **head_to_get** — Converts HEAD requests to GET (body stripped later)
3. **method_override** — Converts POST to PUT/PATCH/DELETE via `_method` param or `X-HTTP-Method-Override` header
4. **match** — Matches the URL to a route, sets `request.matched_route` and `request.matched_params`
5. **redirect** — If the matched route is a redirect, sends the redirect response
6. **dispatch** — Instantiates the controller and calls `_dispatch(action_name)`:
   - Runs **before** callbacks in MRO order
   - If any before callback sets a response body, the action is **skipped silently**
   - Calls the action method
   - Runs **after** callbacks in reverse MRO order
7. **strip_body_if_head** — Removes body for original HEAD requests
8. **update_session_cookie** — Writes back modified session as signed cookie

All steps are logged at DEBUG level with the `proper` logger (prefix `[pipeline]`).

## Controllers

### File Location and Naming

- Controllers live in `myapp/controllers/`
- File: `things_controller.py`, class: `ThingController`
- All controllers in the folder are auto-imported by `controllers/__init__.py`

### Inheritance

Every controller must inherit from `AppController`, which itself inherits from
`Controller` plus any concerns:

```python
class AppController(Controller, OriginProtection, RateLimiting, SecurityHeaders):
    pass

class ThingController(AppController):
    @router.get("things")
    def index(self):
        pass
```

### Implicit Template Rendering

If an action method returns `None` and doesn't set `response.body`, the framework
**automatically infers a template** from the controller's module path:

- `myapp.controllers.things_controller` → `pages/controllers/things/{action}.jinja`
- `myapp.controllers.admin.users_controller` → `pages/controllers/admin/users/{action}.jinja`

The inferred template is logged at DEBUG level: `[Controller.action] rendering inferred template: ...`

To render explicitly, use `self.render("path/to/template.jinja")` or return a value.

### Before/After Callbacks

Callbacks are declared as class attributes and inherited through the MRO:

```python
class MyMixin(Concern):
    before = {"do": "check_something", "only": "create"}
    after = {"do": "log_something", "exclude": "index"}
```

- `only` / `exclude` filter by action name (string or list)
- Multiple callbacks: use a list of dicts
- **If a before callback sets `response.body`, the action is never called** — this is logged
- Callbacks run per-class in MRO order (before) or reverse MRO order (after)

### Rendering Responses

```python
self.render("template.jinja")              # Render a Jx template
self.render(json=data)                     # JSON response
self.render(text="plain text")             #  Plain text response
self.response.redirect_to("Route.action")  # Redirect to a named route
self.response.redirect_to("/path")         # Redirect to a URL
```

### Accessing Request Data

```python
self.params                # MultiDict: merged query + form + route params
self.params["key"]         # Last value for key (not first!)
self.params.getall("key")  # All values for key
self.request.query         # Query string params only
self.request.form          # POST body params only
self.request.session       # Session data (DotDict)
self.defaults              # Route defaults
```

## Routing

### Resource Routes (CRUD)

```python
@router.resource("photos")
class PhotoController(AppController):
    def index(self): ...    # GET    /photos
    def new(self): ...      # GET    /photos/new
    def create(self): ...   # POST   /photos
    def show(self): ...     # GET    /photos/:photo_id
    def edit(self): ...     # GET    /photos/:photo_id/edit
    def update(self): ...   # PATCH  /photos/:photo_id
    def delete(self): ...   # DELETE /photos/:photo_id
```

Only methods that exist on the class get routes. Use `pk=None` for singleton
resources (e.g., `@router.resource("profile", pk=None)`).

### Individual Routes (avoid using them)

Defined as decorators on controller methods:

```python
@router.get("items/:item_id")
def show(self): ...

@router.post("items")
def create(self): ...
```

- Path placeholders: `:name`, `:id<int>`, `:temp<float>`, `:path<path>`.
- You can also specify a regex as placeholder: `:slug<[a-z-]+>`.
- All values are strings unless `<int>` or `<float>` is specified.

### Scoped Routes

```python
admin = router.scope("admin")

@admin.get("dashboard")
def dashboard(self): ...   # GET /admin/dashboard
```

### Named Routes and URL Generation

```python
url_for("Photo.show", photo)       # /photos/42
url_for("Photo.index")             # /photos
url_for("assets", file="app.css")  # /assets/app.css (with fingerprint)
```

## Models

- Use Peewee ORM. All models inherit from `BaseModel` (in `models/base.py`)
- Mixins inherit from `BaseMixin` (same db, but used for multi-table inheritance)
- **Every model must be imported in `models/__init__.py`** for migration detection
- Timestamped mixin adds `created_at` and `updated_at` (auto-updated on save)

```python
from .base import BaseModel
from .concerns.timestamped import Timestamped

class Photo(Timestamped, BaseModel):
    title = pw.CharField()
```

### Migrations

```bash
proper db migrate              # Run pending migrations
proper db create "description" # Create a new migration
proper db rollback             # Rollback last migration
```

Migration files live in `db/main/`.

## Concerns (Mixins)

Concerns add behavior to controllers through before/after callbacks:

Concern            | What it does
------------------ | ---------------------------------------------------------
`OriginProtection` | Validates request origin (Sec-Fetch-Site / Origin header)
`RateLimiting`     | Rate limits by IP or custom key using the cache backend
`SecurityHeaders`  | Sets X-Frame-Options, X-XSS-Protection, Referrer-Policy
`CurrentLocale`    | Determines locale from URL, cookie, user, or Accept-Language
`CurrentTimezone`  | Sets timezone from user attribute

`OriginProtection` is enabled by default in `AppController`. It rejects
cross-origin state-changing requests (POST, PUT, PATCH, DELETE) unless the
origin matches the host or is in `TRUSTED_ORIGINS`.

## Security

### CSRF Protection

The default `AppController` uses `OriginProtection` (header-based). It works automatically.

### Session

- Signed cookie (`_session`), validated with `SECRET_KEYS`
- Session data is a `DotDict` (dot-notation access)
- Flash messages are stored in the session and cleared after one read

### Secret Keys

- Defined in `config/main.py` as a list, **oldest to newest**
- Minimum 48 characters each
- Rotate by appending a new key and later removing the oldest

## Emails

```python
from .base_email import BaseEmail

class WelcomeEmail(BaseEmail):
    subject = "Welcome!"
    def __init__(self, user):
        super().__init__(to=user.email)
        self.body = self.render("emails/welcome.jinja", user=user)

# Send immediately
WelcomeEmail(user).send()

# Send via background queue
WelcomeEmail(user).send_later()
```

## Background Tasks

Tasks are defined in `myapp/tasks/` using Huey:

```python
@app.queue.task()
def process_something(item_id):
    ...
```

## Configuration

All config lives in `myapp/config/`. The `__init__.py` imports modules in order,
and later modules can override earlier values. Config is accessed as:

```python
app.config.DEBUG
app.config.SECRET_KEYS
app.config.DATABASES
```

Environment is set via `APP_ENV` (values: `dev`, `test`, `prod`).

## Running and Testing

```bash
proper run                # Start dev server (port 2300)
make test                 # Run tests (pytest -x)
make lint                 # Run linter (ruff)
proper db migrate         # Run migrations
```

## Logging

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

## CLI

Run `proper` to see the available commands
