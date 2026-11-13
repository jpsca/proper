---
title: Rendering Responses
description: What an action returns: implicit and explicit templates, JSON and text, Turbo Streams, redirects and flash messages, HTTP errors and error handlers, request/response basics
last_verified: 2026-11-13
sources:
  - src/proper/controller
  - src/proper/core/response
  - src/proper/turbo
  - src/proper/errors.py
---

# Rendering Responses

How a controller action produces its response. The controller itself (CRUD, the generated actions, params) is in [controllers.md](controllers.md).

## Table of Contents

- [Rendering Responses](#rendering-responses)
- [Redirecting](#redirecting)
- [Raising HTTP Errors](#raising-http-errors)
- [HTTP Caching](#http-caching)
- [Request and Response Objects](#request-and-response-objects)


## Rendering Responses

### Implicit Template Rendering

If an action returns `None` and doesn't set `response.body`, Proper infers a
template by walking a **prefix chain** (from the controller's MRO) crossed
with **format candidates** (from the `Accept` header). The first template that
exists in the jx catalog wins.

**Step 1 — Build the prefix chain**. Walk `type(self).mro()`
from subclass upward, stopping at `Controller`. For each user-defined class,
take its module, drop the first two dot-separated segments (the layout
assumes `<app>.controllers.<…>`), strip any `_controller` suffix and convert
remaining dots to slashes:

- `myapp.controllers.admin.card_controller` → `admin/card`
- Its parent `myapp.controllers.app_controller` → `app`

So a subclass inherits its ancestors' view folders as fallbacks, with no config.

**Step 2 — Build the format list**. Parse the
request's `Accept` header in priority order; map each mime to a filename
extension via `mimetypes.guess_extension`. Stop at `*/*`, adding
`request.default_format` (default `"html"`) after the formats named before it,
so `application/json, text/plain, */*` yields `json, txt, html`. If no mime had
a known extension, use `default_format` alone.

**Step 3 — Iterate candidates**. For each prefix, emit
every `{prefix}/{action}.{format}.jx` then the bare
`{prefix}/{action}.jx` as a last-resort fallback, before moving to the next
prefix. Example — action `show`, Accept `text/html, application/json`,
prefixes `["admin/card", "app"]`:

```
admin/card/show.html.jx
admin/card/show.json.jx
admin/card/show.jx
app/show.html.jx
app/show.json.jx
app/show.jx
```

**Step 4 — Resolve**. Return the first candidate that exists in the catalog.
If none matches but a template exists for `request.default_format`, the action
has a template the client doesn't accept: the body is empty and the status
becomes `406 Not Acceptable` (kept when it is already an error status, e.g.
404). `ComponentNotFoundError`, listing every candidate tried, is raised only
when the default format has no template either. The prefix chain and the
format list are computed once per controller action and per `Accept` header. The chosen template is logged at DEBUG:
`[Controller.action] rendering inferred template: ...`

Explicit `self.render("some/name.jx")` bypasses this resolution — the name is
passed straight to the jx catalog. The prefix chain and format negotiation
only apply to implicit rendering. For a simpler one-of-two-formats pattern,
see `self.request.format` in "JSON API Patterns" below.

This means the simplest action is one that does nothing:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    # Automatically renders views/card/show.jx
```

### Explicit Template Rendering

Use `self.render()` when you need to render a different template than the default, or when you need to set a custom status code. The `self.redo()` method is a shortcut that re-renders the form template (e.g., `new.jx` for `create`, `edit.jx` for `update`) with a `422 Unprocessable Entity` status. The generated `create` and `update` actions call it when the form is invalid. Always `return` it, because nothing halts inside an action and the code after it would otherwise run:

```python
if self.form.is_invalid:
    return self.redo()
```

The `render()` method returns a string. Return it from the action so it becomes the response body (or assign it to `self.response.body` yourself). Calling it without using the result renders nothing: the implicit template is rendered instead.

### JSON Responses

```python
def show(self):
    card = Card.get_by_id(self.params["card_id"])
    return self.render(json={"id": card.id, "title": card.title})
```

This sets the Content-Type to `application/json` and serializes the data using a custom encoder that handles `date` and `datetime` objects (dates are prefixed with `"__dt__"` for round-trip parsing).

### Turbo Stream Responses

A Turbo form submission (`Accept: text/vnd.turbo-stream.html`) resolves a `{action}.turbo_stream.jx` view automatically, or you build the response inline with `self.render(stream=...)`. Branch on `self.request.turbo_stream` when one URL serves both Turbo and normal clients. See [turbo.md](turbo.md#responding-to-a-form).

### JSON API Patterns

#### Content Negotiation

Use `self.request.format` to serve both HTML and JSON from the same controller:

```python
def show(self):
    self.card = Card.get_or_none(self.params["card_id"])
    if not self.card:
        raise NotFound

    if self.request.format == "json":
        return self.render(json={"id": self.card.id, "title": self.card.title})
    # Otherwise renders show.jx implicitly
```

The `format` property parses the `Accept` header and returns `"html"`, `"json"`, `"xml"`, etc. When the header is missing or ambiguous, it falls back to `request.default_format` (default: `"html"`).

When serving both formats from the same URL, set the `Vary` header so caches distinguish them:

```python
after = {"do": "set_vary"}

def set_vary(self):
    self.response.set_vary("Accept")
```

#### JSON-Only Controllers

For pure API controllers, disable cookie headers since they aren't needed. JSON APIs return error responses as JSON instead of re-rendering a form (`redo()`), so handle validation in the action and return errors directly:

```python
from proper.errors import NotFound


@router.resource("cards")
class CardController(AppController):
    before = {"do": "disable_cookies"}

    def disable_cookies(self):
        self.response.disable_cookies = True

    def index(self):
        cards = Card.select()
        return self.render(json=[
            {"id": c.id, "title": c.title} for c in cards
        ])

    def show(self):
        card = Card.get_or_none(self.params["card_id"])
        if not card:
            raise NotFound
        return self.render(json={"id": card.id, "title": card.title})

    def create(self):
        form = CardForm(self.params)
        if form.is_invalid:
            return self.render(json={"errors": form.errors}, status=422)
        card = form.save()
        return self.render(json={"id": card.id, "title": card.title}, status=201)
```

#### JSON Error Responses

The framework's default error handler renders HTML. For JSON APIs, register a controller-based error handler using `@router.error()`:

```python {title="myapp/controllers/api_error_controller.py"}
from proper import errors
from ..router import router
from .app_controller import AppController


class ApiErrorController(AppController):
    skip_authentication = True

    @router.error(errors.NotFound)
    def not_found(self):
        return self.render(json={"error": "not found"}, status=404)

    @router.error(errors.Forbidden)
    def forbidden(self):
        return self.render(json={"error": "forbidden"}, status=403)

    @router.error(Exception)
    def error(self):
        return self.render(json={"error": "internal server error"}, status=500)
```

#### XHR Detection

For Turbo or AJAX requests that send `X-Requested-With: XMLHttpRequest`, branch inside the action to return JSON errors for XHR requests while keeping the default re-render for regular form submissions:

```python
def create(self):
    self.form = CardForm(self.params)
    if self.form.is_invalid:
        if self.request.is_xhr:
            return self.render(json={"errors": self.form.errors}, status=422)
        return self.redo()
    card = self.form.save()
    self.response.redirect_to("Card.show", card, flash="Card was created")
```

### Plain Text Responses

```python
def healthcheck(self):
    return self.render(text="ok")
```

This sets the Content-Type to `text/plain`.

### Setting a Custom Status

You can set the status in the response object:

```python
from proper import status

self.response.status = status.im_a_teapot
```

All render modes also accept a `status` parameter:

```python
return self.redo(status=status.conflict)
return self.render(json={"error": "not found"}, status=status.not_found)
return self.render(text="created", status=status.created)
```

Status codes are imported from `proper.status` as integers (e.g., `proper.status.unprocessable` is `422`).

### Return Values

If an action returns a value (any non-`None` value), that value becomes the response body directly:

```python
def show(self):
    return "Hello, world!"    # Sent as the response body
```

### Template Variables

All instance attributes set on the controller are passed to the template as variables. Implementation: `Controller.render` calls `catalog.render(name, **vars(self))`, so anything in the instance's `__dict__` becomes a template kwarg.

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.related = Card.select().where(Card.category == self.card.category).limit(5)
    # {{ card }} and {{ related }} are now available in the template
```

`request` and `response` are also in `vars(self)` (set in `Controller.__init__`) and reachable as `{{ request }}` / `{{ response }}` in templates. Class-level **properties** like `self.app` and `self.params` are *not* in `vars(self)` — for those, templates use `current.app` and `current.request` (which exposes the same data). There is no automatic exclusion of underscore-prefixed names; `self._foo = ...` would be reachable as `{{ _foo }}` in the template.


## Redirecting

Use `self.response.redirect_to()` to redirect the user to another URL or named route:

```python
# Redirect to a named route
self.response.redirect_to("Card.show", card_id=card.id)

# Redirect to a named route with an object
self.response.redirect_to("Card.show", card)

# Redirect to a path (anything starting with `/` or `http` is a URL, not a route name)
self.response.redirect_to("/dashboard")

# Redirect to an external URL
self.response.redirect_to("https://example.com")
```

By default, redirects use the status `303 See Other`, which is the correct status for redirecting after a POST. You can change this with the `status` parameter:

```python
from proper import status

self.response.redirect_to("/new-location", status=status.moved_permanently)
```

When using `url_for` or `redirect` for a route with arguments, prefer passing an object instead of individual arguments. For example, do `url_for('Post.edit', post)` instead of `url_for('Post.edit', id=post.id)`.


### Flash Messages

Flash messages are one-time messages that survive a single redirect. They are stored in the session and displayed on the next page load. You can set a flash message when redirecting:

```python
self.response.redirect_to(
    "Card.index",
    flash="Card was deleted",
)

self.response.redirect_to(
    "Session.new",
    flash="Try again in a few minutes.",
    flash_cat="negative",
)
```

The `flash_cat` parameter defaults to `"positive"`. Common categories are `"positive"`, `"negative"`, `"warning"`, and `"info"` — your layout decides how each one looks.

You can also set flash messages directly without redirecting:

```python
self.response.flash("positive", "Settings saved")
```

In your templates, flash messages are reachable through `current.request.flashes` — a list of `(type, message)` tuples. The generated `flashes.jx` does roughly `{% set flashes = current.request.flashes %}` and iterates. Storage is the session, but the access path on the read side is the request.


## Raising HTTP Errors

To halt processing and return an HTTP error response, raise one of the error classes from `proper.errors`. The framework will catch the exception, look for a registered error handler, and render the appropriate error page:

```python
from proper.errors import NotFound, Forbidden

def show(self):
    card_id = self.params.get("card_id", "")
    if not card_id.isdigit():
        raise NotFound
    self.card = Card.get_or_none(int(card_id))
    if not self.card:
        raise NotFound

def update(self):
    if not self.card.editable_by(current.user):
        raise Forbidden("You don't have permission to edit this card")
```

### Available Error Classes

| Status | Class                        | When to use                                                      |
|--------|------------------------------|------------------------------------------------------------------|
| 400    | `BadRequest`                 | Malformed request data                                           |
| 401    | `Unauthorized`               | Missing authentication                                           |
| 403    | `Forbidden`                  | Authenticated but not authorized                                 |
| 400    | `MultipartError`             | Malformed multipart/urlencoded/JSON body, or over the form limits (a `BadRequest`) |
| 403    | `InvalidOrigin`              | Raised by `OriginProtection`                                     |
| 403    | `MissingCSRFToken` / `InvalidCSRFToken` | Raised by `RequestForgeryProtection`                  |
| 404    | `NotFound`                   | Record or page doesn't exist                                     |
| 404    | `MatchNotFound`              | No route matched (a `NotFound`)                                  |
| 405    | `MethodNotAllowed`           | Wrong HTTP method (raised by the router; sets the `Allow` header) |
| 406    | `NotAcceptable`              | No representation matches the `Accept` header                    |
| 409    | `Conflict`                   | Conflicting state (e.g., duplicate)                              |
| 410    | `Gone`                       | Resource permanently removed                                     |
| 413    | `RequestEntityTooLarge`      | Body exceeds `MAX_CONTENT_LENGTH`                                |
| 414    | `UriTooLong`                 | Query exceeds `MAX_QUERY_SIZE`                                   |
| 415    | `UnsupportedMediaType`       | Unknown `charset` in a form/JSON body                            |
| 422    | `UnprocessableEntity`        | Valid syntax but semantic errors                                 |
| 429    | `TooManyRequests`            | Rate limit exceeded (raised by the `RateLimiting` concern)       |
| 451    | `UnavailableForLegalReasons` |                                                                  |
| 500    | `InternalServerError`        | Something went wrong on the server (aliases: `ServerError`, `Error`) |

All inherit from `HTTPError`. Each has a `status` attribute and an optional message. `proper.errors` also has the rarer ones (`LengthRequired` 411, `PreconditionFailed` 412, `RangeNotSatisfiable` 416, `FailedDependency` 424, `PreconditionRequired` 428, `HTTPNotImplemented` 501, `InsufficientStorage` 507, `NetworkAuthenticationRequired` 511) and the `BadRequest` subclasses `InvalidHeader`, `MissingHeader`, `BadRequestKeyError` and `ClientDisconnected`.

### Registering Error Handlers

You can register controller methods to handle specific exceptions. When that exception is raised anywhere during request processing, Proper instantiates the controller and calls the registered method. Handlers run only when `DEBUG` is off; in debug mode the framework's debug page is shown instead:

```python {title="myapp/controllers/public_controller.py"}
from proper import errors
from ..router import router
from .app_controller import AppController


class PublicController(AppController):
    @router.error(errors.NotFound)
    @router.get("_not_found")
    def not_found(self):
        pass

    @router.error(Exception)
    @router.get("_error")
    def error(self):
        pass
```

The `@router.error()` decorator registers the handler, and the `@router.get()` decorator creates a route to preview the error page during development (e.g., visiting `/_not_found` in the browser). You can stack both decorators on the same method.

If several handlers match an error, the most specific one wins: the one for the closest class in the error's hierarchy, as with `except` clauses. The order of registration doesn't matter, so a `MatchNotFound` goes to the `NotFound` handler even if the `Exception` handler was registered first.


## HTTP Caching

`self.fresh_when(obj_or_collection)` sets `ETag`/`Last-Modified` and turns the response into a `304 Not Modified` when the client already has it. The options and the freshness rules are in [caching.md](caching.md#http-caching).


## Request and Response Objects

The `self.request` and `self.response` objects are available in every controller action. For the full attribute/method reference, see [reference/api.md](reference/api.md#request) and [reference/api.md](reference/api.md#response). Here's a quick overview of the most common usage:

```python
# Request basics
self.request.method           # "GET", "POST", etc.
self.request.path             # "/cards/42"
self.request.query            # Query string params (MultiDict)
self.request.form             # POST body params (MultiDict)
self.request.session          # Session data (dict)
self.request.headers          # Request headers
self.request.format           # "html", "json", etc. (from Accept header)
self.request.is_xhr           # True if X-Requested-With: XMLHttpRequest
self.request.remote_ip        # Client IP address (forwarding headers only from TRUSTED_PROXIES)
self.request.request_id       # X-Request-ID header (cleaned) or a new UUID; sent back in the response
self.request.get_cookie("theme", default="light")
self.request.get_signed_cookie("_token", max_age=2592000)

# Response basics
self.response.status = 201
self.response.headers["X-Custom"] = "value"
self.response.set_cookie("theme", "dark", max_age=31536000, secure=True, httponly=True)
self.response.set_signed_cookie("_auth", token, max_age=2592000, httponly=True)
self.response.unset_cookie("old_cookie")
self.response.set_cache_control("max-age=3600", "public")
self.response.send_file("/path/to/report.pdf", as_attachment=True, download_name="Q4-Report.pdf")
```
