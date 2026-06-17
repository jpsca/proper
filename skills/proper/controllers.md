---
title: Controllers
description: Controller fundamentals — CRUD, callbacks, parameters, rendering, redirects, concerns
last_verified: 2026-06-03
---

# Controllers

## Table of Contents

- [Introduction](#introduction)
- [The Core Principle: Everything is CRUD](#the-core-principle-everything-is-crud)
- [The Generated Controller](#the-generated-controller)
- [Parameters](#parameters)
- [Sessions](#sessions)
- [Rendering Responses](#rendering-responses)
- [Redirecting](#redirecting)
- [Raising HTTP Errors](#raising-http-errors)
- [HTTP Caching](#http-caching)
- [Request and Response Objects](#request-and-response-objects)
- [Controller Callbacks](#controller-callbacks)
- [Concerns](#concerns)
- [Adding More Actions](#adding-more-actions)


## Introduction

A controller is responsible for processing the request and generating the appropriate output.
They are defined in individual files (one for each class) inside the `myapp/controllers/` folder (or a subfolder).
They must be imported in the `myapp/controllers/__init__.py` file.

It is customary for controllers that:

* Their names are **singular** ("PhotoController" instead of "PhotosController")
* Their names are suffixed with "Controller"
* Their files are named with the same name in snake-case, including the "controller" suffix. File: `thing_controller.py`, class: `ThingController`.

Every controller must inherit from `AppController`, which itself inherits from
`Controller` plus any concerns:

```python
from proper import Controller
from proper.concerns import OriginProtection, RateLimiting

from .concerns.form_validation import FormValidation
from .concerns.security_headers import SecurityHeaders


class AppController(
    Controller,
    OriginProtection,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
):
    pass
```

```python
from ..router import router
from .app_controller import AppController


class ThingController(AppController):
    @router.get("things")
    def index(self):
        pass
```

## Adding a controller

To generate a controller WITH a model (aka: a "resource") **ALWAYS** use the command `proper g resource NAME ...`.

To generate a controller WITHOUT a model **ALWAYS** use the command `proper g controller NAME ...`.

In both cases, in addition to the controller file, a form and several view files will be generated as well. Edit them as needed.

Read the output of `proper g resource --help`, `proper g controller --help`, and  `proper g model --help` to see all the options.

If you are only adding a model, use the model generator `proper g model NAME ...` instead.

## The Core Principle: Everything is CRUD

The `router.resource` class decorator is the most common method to mount a controller in the right URLs.
This decorator maps the `index`, `new`, `create`, `show`, `edit`, `update`, and `delete` methods of the controller class (if they exist) to CRUD actions with the same name.

```python {title="myapp/controllers/card_controller.py"}
from ..router import router
from .app_controller import AppController

@router.resource("cards")
class CardController(AppController):

    # GET /cards
    def index(self):
        """A list of all cards"""

    # GET /cards/new
    def new(self):
        """Show a form for a new card"""

    # POST /cards
    def create(self):
        """Create a card"""

    # GET /cards/:card_id
    def show(self):
        """Show a specific card"""

    # GET /cards/:card_id/edit
    def edit(self):
        """Page for editing a card"""

    # PATCH /cards/:card_id
    def update(self):
        """Update a card"""

    # DELETE /cards/:card_id
    def delete(self):
        """Delete a card"""

```

The auto-generated URLs in this example are:

| HTTP     | PATH                 | ACTION   | USED FOR
| -------- | -------------------- | -------- | -------------------------------
| GET      | /cards               | index    | a list of all cards
| GET      | /cards/new           | new      | form for creating a new card
| POST     | /cards               | create   | create a new card
| GET      | /cards/:card_id      | show     | show a specific card
| GET      | /cards/:card_id/edit | edit     | form for editing a specific card
| PATCH    | /cards/:card_id      | update   | update a specific card
| PUT      | /cards/:card_id      | update   | replace a specific card
| DELETE   | /cards/:card_id      | delete   | delete a specific card

::: warning
If one of those methods doesn't exist in the controller class, its URL is not created.
:::


### ID parameter

The `:card_id` parameter is auto-generated from the singular of the snake-cased controller name (after removing the "Controller" suffix).

Examples:

* `CardController` -> `card_id`
* `UserPhotoController` -> `user_photo_id`

It can also be manually specified with the `pk` argument. Whatever you pass becomes the parameter name verbatim — Proper does not append `_id`. For example, `router.resource("cards", pk="object")` produces URLs like `/cards/:object` and the parameter is read as `self.params["object"]`. If you want an `_id` suffix, include it yourself: `pk="object_id"`.

The ID parameter can be also disabled by using `pk=None`. This is desirable for resources that clients always look up without referencing an ID.

Example: `@router.resource("profile", pk=None)` will generate the following URLs:

| HTTP     | PATH                | ACTION   | USED FOR
| -------- | ------------------- | -------- | -------------------------------
| GET      | /profile/new        | new      | form for creating the profile
| POST     | /profile            | create   | create the profile
| GET      | /profile            | show     | show the profile
| GET      | /profile/edit       | edit     | form for editing the profile
| PATCH    | /profile            | update   | update the profile
| PUT      | /profile            | update   | replace the profile
| DELETE   | /profile            | delete   | delete the profile

Note that the `index` method is ignored when the ID parameter is disabled.


### Manually defined URLs

It is also possible to add routes for individual methods using the decorators `router.get`, `router.post`, `router.patch`, and `router.delete`, for example:

```python {title="myapp/controllers/public_controller.py"}
from ..router import router
from .app_controller import AppController

class PublicController(AppController):
    @router.get("")
    def index(self):
        pass

```

::: warning
This should be used only for exceptional cases, such as the home page.
:::


## The Generated Controller

When you run `proper g resource Card title:str body:text`, Proper generates a controller with the full CRUD pattern. Here's what it looks like (simplified):

```python {title="myapp/controllers/card_controller.py"}
from proper.errors import NotFound

from ..forms.card import CardForm
from ..models import Card
from ..router import router
from .app_controller import AppController


@router.resource("cards")
class CardController(AppController):
    before = [
        {"do": "set_card", "exclude": ["index", "new", "create"]},
        {"do": "set_form", "exclude": ["index", "show", "delete"]},
        {"do": "validate_form", "only": ["create", "update"]},
    ]

    def index(self):
        self.cards = Card.select()

    def show(self):
        pass

    def new(self):
        pass

    def edit(self):
        pass

    def create(self):
        card = self.form.save()
        self.response.redirect_to("Card.show", card, flash="Card was created")

    def update(self):
        card = self.form.save()
        self.response.redirect_to("Card.show", card, flash="Card was updated")

    def delete(self):
        if self.card:    # deleting twice does not fail
            self.card.delete_instance()
        self.response.redirect_to("Card.index", flash="Card was deleted")

    # Private

    def set_card(self):
        card_id = self.params.get("card_id", "")
        self.card = Card.get_or_none(id=int(card_id))
        if self.request.matched_action != "delete" and not self.card:
            raise NotFound

    def set_form(self):
        obj = getattr(self, "card", None)
        self.form = CardForm(self.params, object=obj)
```

Key patterns to notice:

- The `before` list runs in declaration order. `set_card` runs first (when it applies), then `set_form`, then `validate_form`. Each callback narrows its scope with `only` or `exclude` rather than checking `self.request.matched_action` inside the method.
- `set_card` loads the existing record. It is excluded from `index`, `new`, and `create` because those actions don't have an existing record to operate on.
- `set_form` instantiates the form with the request params and the loaded object (if any). It is excluded from `index`, `show`, and `delete`. For `new` and `create`, no card has been loaded, so `obj` is `None`.
- `validate_form` comes from the `FormValidation` concern. On `create` and `update`, if the form is invalid it calls `self.redo()` to re-render the form template with a `422 Unprocessable Entity` status, and the action never runs.
- After a successful create, update, or delete, the controller redirects with a flash message.
- The `delete` action checks `if self.card` to handle the case where someone deletes the same record twice (e.g., double-clicking the delete button).
- `form.save()` validates the data, persists the model (creating or updating), and returns it — no follow-up `obj.save()` needed. See [Forms — Saving](./forms.md) for details on the integration with Peewee.

### Data Flow: params → set_card → set_form → validate_form → action → save

This is the complete path data takes through a create or update action.

**Create** (`POST /cards`):

```
self.params  (merged MultiDict: query + form body + route params)
        │
        ▼
set_card  (skipped — excluded for create)
        │
        ▼
set_form
  └─ self.form = CardForm(self.params, object=None)
        │
        ▼
validate_form
  ├─ form valid    → falls through
  └─ form invalid  → self.redo() re-renders new.jx with 422
                       (action never runs)
        │
        ▼
create action
  └─ card = self.form.save()              # build a new Card from validated data
  └─ card.save()                           # INSERT into DB
  └─ redirect_to("Card.show", card)
```

**Update** (`PATCH /cards/:card_id`):

```
self.params
        │
        ▼
set_card
  └─ self.card = Card.get_or_none(id=int(card_id))
  └─ raises NotFound if missing
        │
        ▼
set_form
  └─ obj = self.card  (loaded above)
  └─ self.form = CardForm(self.params, object=obj)
       Fields pre-filled from self.card; submitted params override
        │
        ▼
validate_form  (same pipeline as create)
        │
        ▼
update action
  └─ card = self.form.save()              # mutates self.card in memory
  └─ card.save()                           # UPDATE in DB
  └─ redirect_to("Card.show", card)
```

The key difference: on create, `form.save()` instantiates a **new** model. On update, it mutates the **existing** object passed in as `object=self.card`.

## Namespacing controllers

When you need a separate controller for the same resource — for example, an admin interface alongside a public one — namespace the controller under a subfolder. This gives the namespaced controller its own routes, forms, and views without conflicting with the public version.

**ALWAYS** generate a namespaced controller using the commands:

- `proper g resource NAME --namespace=NAMESPACE`, if you need to add a model as well; or
- `proper g controller NAME --namespace=NAMESPACE` for just the controller, form, and views.


### What the generator creates

For `proper g controller Post --namespace=admin`:

```
myapp/
├── controllers/
│   ├── __init__.py               # Modified: adds `from .admin import post_controller`
│   └── admin/
│       ├── __init__.py
│       └── post_controller.py
├── forms/
│   └── admin/
│       ├── __init__.py
│       └── post.py
└── views/
    └── admin/
        └── post/
            ├── index.jx
            ├── show.jx
            ├── new.jx
            ├── edit.jx
            └── form.jx
```


### The scoped router

The generator adds a scoped router to `router.py`:

```python {title="myapp/router.py"}
admin_router = router.scope("admin")
```

The namespaced controller uses this scoped router instead of the root one. All routes are automatically prefixed with `/admin`:

```python {title="myapp/controllers/admin/post_controller.py"}
from myapp.forms.admin.post import PostForm
from myapp.models import Post
from myapp.router import admin_router
from ..app_controller import AppController


@admin_router.resource("posts")
class PostController(AppController):
    before = [
        {"do": "set_post", "exclude": ["index", "new", "create"]},
        {"do": "set_form", "exclude": ["index", "show", "delete"]},
        {"do": "validate_form", "only": ["create", "update"]},
    ]

    def index(self):
        self.posts = Post.select()

    def show(self):
        pass

    def new(self):
        pass

    def edit(self):
        pass

    def create(self):
        post = self.form.save()
        post.save()
        self.response.redirect_to(
            "Admin:Post.show", post,
            flash="Post was created",
        )

    # ... other actions ...

    def set_post(self):
        post_id = self.params.get("post_id", "")
        self.post = Post.get_or_none(id=int(post_id))
        if self.request.matched_action != "delete" and not self.post:
            raise NotFound

    def set_form(self):
        obj = getattr(self, "post", None)
        self.form = PostForm(self.params, object=obj)
```


### Namespaced route names

Route names are prefixed with the namespace in PascalCase, separated by a colon:

| Method | Path | Named route |
|--------|------|-------------|
| GET | `/admin/posts` | `Admin:Post.index` |
| GET | `/admin/posts/new` | `Admin:Post.new` |
| POST | `/admin/posts` | `Admin:Post.create` |
| GET | `/admin/posts/:post_id` | `Admin:Post.show` |
| GET | `/admin/posts/:post_id/edit` | `Admin:Post.edit` |
| PATCH | `/admin/posts/:post_id` | `Admin:Post.update` |
| DELETE | `/admin/posts/:post_id` | `Admin:Post.delete` |

Use these prefixed names for `url_for` and `redirect_to`:

```python
app.url_for("Admin:Post.index")               # /admin/posts
app.url_for("Admin:Post.show", post)           # /admin/posts/42
self.response.redirect_to("Admin:Post.show", post, flash="Done")
```

In templates:

```html+jinja
<a href="{{ url_for('Admin:Post.index') }}">Manage Posts</a>
```


### The model is shared

Namespaced controllers import the model from the same `models/` directory as all other controllers. The namespace only affects controllers, forms, and views — not models. This means both the public `PostController` and the admin `PostController` operate on the same `Post` model.


### Imports

The namespaced controller is imported through the root `controllers/__init__.py`:

```python {title="myapp/controllers/__init__.py"}
from .public_controller import *  # noqa
from .post_controller import *  # noqa
from .admin import post_controller  # noqa
```


## Parameters

Data sent by the incoming request is available in your controller via `self.params`. This is a `MultiDict` that merges three sources in order:

1. **Query string parameters** - from the URL (e.g., `?filter=free`)
2. **Form body parameters** - submitted from an HTML form
3. **Route parameters** - extracted from the URL path (e.g., `:card_id`)

Route parameters have the highest priority and will override query and form values with the same name.

```python
@router.resource("clients")
class ClientController(AppController):

    # This action receives query string parameters from an HTTP GET request
    # at the URL "/clients?status=activated"
    def index(self):
        if self.params.get("status") == "activated":
            self.clients = Client.get_activated()
        else:
            self.clients = Client.get_inactivated()

    # This action receives form data from a POST request to "/clients"
    def create(self):
        client = self.form.save()
        client.save()
        self.response.redirect_to("Client.show", client, flash="Client was created")
```

### Params Quick Reference

```python
self.params                # MultiDict: merged query + form + route params
self.params.get("key")     # Value for key, or None
self.params["key"]         # Value for key (raises KeyError if missing)
self.params.getall("key")  # All values for key (HTML forms can send multiple)
```

Because `self.params` is a `MultiDict`, `self.params["key"]` returns the **last** value for that key, not the first. Use `self.params.getall("key")` when a form sends multiple values for the same name (e.g., checkboxes).

### Accessing Sources Individually

If you need to distinguish where a parameter came from:

```python
self.request.query         # Query string params only (MultiDict)
self.request.form          # POST body params only (MultiDict, includes file uploads)
self.request.matched_params  # Route params only (dict)
```

### Route Defaults

Routes can define default values that are available in the controller via `self.defaults`:

```python
# In the router:
@router.get("pages/:slug", defaults={"sidebar": True})
def show(self): ...

# In the controller:
self.defaults["sidebar"]   # True
```


## Sessions

Session data is stored in a signed cookie and is available on both the request and response objects:

```python
# Read session data (set by a previous request)
user_id = self.request.session.get("user_id")
locale = self.request.session.locale    # DotDict supports attribute access

# Write session data (will be sent in the response cookie)
self.response.session["user_id"] = user.id
self.response.session.locale = "es"
```

The session is a `DotDict`, so you can use both dict-style and attribute-style access. Read from `self.request.session`, write to `self.response.session`. The framework compares the two at the end of the request and only updates the cookie if the session changed.


## HTTP Method Override

HTML forms only support `GET` and `POST`. To work around the spec, Proper rewrites the request method when a `POST` carries a `_method` value naming a different verb. This is what makes `<Form method="patch">` work (the form is wire-encoded as `POST` with `_method=patch`).

Implementation: `proper.pipeline.method_override` runs before routing. For an incoming `POST` request, it looks for a method override in three places, in order:

1. The `X-HTTP-Method-Override` header.
2. The `_method` query string parameter.
3. The `_method` form field.

The override only applies when the value (uppercased) is one of `PUT`, `PATCH`, `DELETE`, or `QUERY`. The pipeline rewrites `request.method` before the router sees it, so route definitions like `@router.patch("cards/:card_id")` match the rewritten method.

Only `POST` is rewritten — a `GET` carrying `_method=delete` is *not* rewritten (this stops misbehaving links from triggering destructive actions).

The rendered HTML for `<Form method="patch">` is:

```html
<form method="post" action="..." novalidate>
  <input type="hidden" name="_method" value="patch">
  ...
</form>
```


## Rendering Responses

### Implicit Template Rendering

If an action returns `None` and doesn't set `response.body`, Proper infers a
template by walking a **prefix chain** (from the controller's MRO) crossed
with **format candidates** (from the `Accept` header). The first template that
exists in the jx catalog wins.

**Step 1 — Build the prefix chain** (`Controller._prefixes`). Walk `type(self).mro()`
from subclass upward, stopping at `Controller`. For each user-defined class,
take its module, drop the first two dot-separated segments (the layout
assumes `<app>.controllers.<…>`), strip any `_controller` suffix and convert
remaining dots to slashes:

- `myapp.controllers.admin.card_controller` → `admin/card`
- Its parent `myapp.controllers.app_controller` → `app`

So a subclass inherits its ancestors' view folders as fallbacks, with no config.

**Step 2 — Build the format list** (`iter_format_extensions`). Parse the
request's `Accept` header in priority order; map each mime to a filename
extension via `mimetypes.guess_extension`. Stop at `*/*`. If nothing matches,
use `request.default_format` (default `"html"`).

**Step 3 — Iterate candidates** (`iter_candidates`). For each prefix, emit
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

**Step 4 — Resolve**. Return the first candidate where `catalog.has(name)` is
true. If none match, raise `ComponentNotFoundError` listing every candidate
tried. The chosen template is logged at DEBUG:
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

Use `self.render()` when you need to render a different template than the default, or when you need to set a custom status code. The `self.redo()` method is a shortcut that re-renders the form template (e.g., `new.jx` for `create`, `edit.jx` for `update`) with a `422 Unprocessable Entity` status. The generated `validate_form` callback (from the `FormValidation` concern) calls it for you on invalid submissions, but you can also call it manually:

```python
# Re-render the form template with a 422 status
self.redo()
```

The `render()` method returns a string that becomes the response body when returned from the action. You can also call it without returning — it sets the body directly.

### JSON Responses

```python
def show(self):
    card = Card.get_by_id(self.params["card_id"])
    return self.render(json={"id": card.id, "title": card.title})
```

This sets the Content-Type to `application/json` and serializes the data using a custom encoder that handles `datetime` objects (dates are prefixed with `"__dt__"` for round-trip parsing).

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

For pure API controllers, disable cookie headers since they aren't needed. Don't register `validate_form` either — JSON APIs return error responses as JSON instead of re-rendering a form, so handle validation in the action and return errors directly:

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
        card.save()
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

For Turbo or AJAX requests that send `X-Requested-With: XMLHttpRequest`, you can override `validate_form` to return JSON errors for XHR requests while keeping the default re-render for regular form submissions:

```python
def validate_form(self):
    form = getattr(self, "form", None)
    if form and form.is_invalid:
        if self.request.is_xhr:
            return self.render(json={"errors": form.errors}, status=422)
        self.redo()
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
return self.redo()
return self.render(json={"error": "not found"}, status=not_found)
return self.render(text="created", status=created)
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

# Redirect to an absolute URL
self.response.redirect_to("/dashboard")

# Redirect to an external URL
self.response.redirect_to("https://example.com")
```

By default, redirects use the status `303 See Other`, which is the correct status for redirecting after a POST. You can change this with the `status` parameter:

```python
from proper import status

self.response.redirect_to("/new-location", status=status.moved_permanently)
```

When using `url_for` or `redirect` for a route with arguments, prefer passing an object instead of indivual arguments. For example, do `url_for('Post.edit', post)` instead of `url_for('Post.edit', id=post.id)`.


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
self.response.flash.message("success", "Settings saved")
```

In your templates, flash messages are reachable through `current.request.flashes` — a list of `(type, message)` tuples. The generated `flashes.jx` does roughly `{% set flashes = current.request.flashes %}` and iterates. Storage is the session, but the access path on the read side is the request.


## Raising HTTP Errors

To halt processing and return an HTTP error response, raise one of the error classes from `proper.errors`. The framework will catch the exception, look for a registered error handler, and render the appropriate error page:

```python
from proper.errors import NotFound, Forbidden

def set_card(self):
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

| Class                         | Status Code | When to use
| ----------------------------- | ----------- | -----------
| `BadRequest`                  | 400         | Malformed request data
| `Unauthorized`                | 401         | Missing authentication
| `Forbidden`                   | 403         | Authenticated but not authorized
| `NotFound`                    | 404         | Record or page doesn't exist
| `MethodNotAllowed`            | 405         | Wrong HTTP method (raised by router)
| `NotAcceptable`               | 406         | No representation matches the `Accept` header
| `Conflict`                    | 409         | Conflicting state (e.g., duplicate)
| `Gone`                        | 410         | Resource permanently removed
| `UnprocessableEntity`         | 422         | Valid syntax but semantic errors
| `TooManyRequests`             | 429         | Rate limit exceeded (raised by RateLimiting concern)
| `InternalServerError`         | 500         | Something went wrong on the server

All error classes inherit from `proper.errors.HTTPError` and accept an optional message string.

### Registering Error Handlers

You can register controller methods to handle specific exceptions. When that exception is raised anywhere during request processing, Proper instantiates the controller and calls the registered method:

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


## HTTP Caching

Proper has built-in support for conditional GET requests using ETag and Last-Modified headers. This happens automatically in the dispatch flow: after calling an action, the framework checks if the response is "fresh" (the client already has the latest version). If so, it returns a `304 Not Modified` with an empty body instead of the full response.

### fresh_when

Use `self.response.fresh_when()` to set caching headers. You can pass model objects with an `updated_at` attribute, and Proper will use the most recent one to generate both the ETag and Last-Modified headers:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.response.fresh_when(self.card)
```

For collections:

```python
def index(self):
    self.cards = Card.select().order_by(Card.created_at.desc())
    self.response.fresh_when(self.cards)
```

Proper uses the maximum `updated_at` value from the collection.

You can also set the ETag and Last-Modified explicitly:

```python
self.response.fresh_when(etag="v1-abc123", last_modified=some_datetime)
```

Options:

```python
self.response.fresh_when(
    self.card,
    strong=True,     # Use a strong ETag (default: weak)
    public=True,     # Allow proxy caches (default: private)
)
```

If `fresh_when()` determines the response is fresh, the action's rendered output is discarded and a `304 Not Modified` is returned automatically. You don't need to check the return value.


## Request and Response Objects

The `self.request` and `self.response` objects are available in every controller action. For the full attribute/method reference, see [api.md](api.md#request) and [api.md](api.md#response). Here's a quick overview of the most common usage:

```python
# Request basics
self.request.method           # "GET", "POST", etc.
self.request.path             # "/cards/42"
self.request.query            # Query string params (MultiDict)
self.request.form             # POST body params (MultiDict)
self.request.session          # Session data (DotDict)
self.request.headers          # Request headers
self.request.format           # "html", "json", etc. (from Accept header)
self.request.is_xhr           # True if X-Requested-With: XMLHttpRequest
self.request.remote_ip        # Client IP address
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


## Controller Callbacks

Controller callbacks are methods that automatically run before and/or after a controller action. A callback can be defined in a controller or in a parent class like `AppController`. Since all controllers inherit from `AppController`, callbacks defined there will run on every controller in your application.

```python
class MyMixin(Concern):
    before = {"do": "check_something", "only": "create"}
    after = {"do": "log_something", "exclude": "index"}
```

- `do` - the name of the method to call (required)
- `only` - run the callback only for these actions (string or list)
- `exclude` - run the callback for all actions except these (string or list)
- Multiple callbacks: use a list of dicts
- **If a before callback sets `response.body` (including via a redirect), the action is never called**
- Before callbacks run outer-first: parent class → child class. After callbacks run inner-first: child class → parent class. Concerns mixed into a parent count as "outer" relative to the child controller.

### `before` callback

Callback methods registered via `before` run before a controller action. They may halt the request cycle if they set a body or a redirect.
A common use case for `before` is ensuring that a user is logged in:

```python
from proper import Controller

class AppController(Controller):
    before = {"do": "require_login"}

    def require_login(self):
        if not current.auth_session:
            self.response.redirect_to("Session.new")
```

The method redirects to the login form if the user is not already logged in. When a `before` callback renders or redirects (like in the example above), the original controller action is not run. If there are additional callbacks registered to run, they are also cancelled and not run.

The `"do"` argument must be a name or a list of names of methods defined in the class or in one of its parent classes.

Another common use is to load an object from the database:

```python
from .app_controller import AppController

class CardController(AppController):
    before = {"do": "set_card", "only": ["show", "edit", "update", "delete"]}

    def set_card(self):
        card_id = self.params.get("card_id")
        self.card = Card.get_or_none(card_id)
        if not self.card:
            raise NotFound

```

In this example, there is no point of trying to load a card in the "index" or "new" actions, there is not even a "card_id" parameter available.
The `only` option runs the callback only for the listed actions; there is also an `exclude` option which works the other way.

::: warning
**If a before callback sets `response.body`, the action is never called** — this is logged.
:::

### `after` callback

You can also define action callbacks to run after a controller action has been executed with the `after` callback.

The `after` callbacks are similar to the `before` callbacks, but because the controller action has already been run they have access to the response data that's about to be sent to the client. A common use case is setting response headers:

```python
class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

::: warning
`after` callbacks are executed only after a successful controller action, and not if an exception is raised in the request cycle.
:::


### Multiple callbacks

Both `before` and `after` callbacks can be written as list of dictionaries, to have many callbacks with different options in the same controller. The callbacks will be executed in MRO order.

```python
from .app_controller import AppController

class CardController(AppController):
    before = [
        {"do": "set_card", "exclude": ("index", "new", "create")},
        {"do": "ensure_editor_access", "only": ["edit", "update", "delete"]},
    ]

    ...
```

### Inheritance

The `before` and `after` callbacks are always inherited and are not obscured by new declarations. Invoking an action in a controller with `before` callbacks defined, will first call any `before` callbacks defined in its parent classes, and then the ones defined in the controller class itself.

For example, if `AppController` has a `before` callback that checks authentication, and `CardController` has a `before` callback that loads a card, both will run — the authentication check first (from the parent), then the card loading (from the child).


## Concerns

A controller concern is a mixin class that defines callbacks and methods that can be shared across multiple controllers. Concern classes inherit from `proper.Concern` and follow the same `before`/`after` callback pattern as controllers.

The convention is to declare them in the `myapp/controllers/concerns/` directory, one per file.

### Writing a Concern

```python {title="myapp/controllers/concerns/team_scoped.py"}
from proper import Concern
from proper.errors import NotFound
from ...models import Team


class TeamScoped(Concern):
    before = {"do": "set_team"}

    def set_team(self):
        team_id = self.params.get("team_id")
        self.team = Team.get_or_none(team_id)
        if not self.team:
            raise NotFound
```

Then mix it into any controller that needs it:

```python
class ProjectController(TeamScoped, AppController):
    # self.team is available in all actions
    def index(self):
        self.projects = self.team.projects
```

### Built-in Concerns

These concerns are available from `proper.concerns`:

#### OriginProtection

Verifies that state-changing requests (POST, PATCH, PUT, DELETE) come from the same origin or a trusted origin. This is the modern CSRF protection approach that doesn't require tokens.

The verification algorithm:

1. Allow all GET, HEAD, OPTIONS, and QUERY requests (safe methods).
2. If neither `Sec-Fetch-Site` nor `Origin` headers are present, allow the request (not a browser request).
3. If the `Origin` header matches the `TRUSTED_ORIGINS` config, allow the request.
4. If `Sec-Fetch-Site` is `same-origin` or `none`, allow the request (modern browsers).
5. If the `Origin` host matches the request's `Host`, allow the request (HTTP or old browsers).
6. If both the `Origin` and the `Host` are on the local network (private IPs, loopback, or link-local addresses), allow the request.
7. Otherwise, raise `InvalidOrigin` (403 Forbidden).

Configuration:

```python
# config/main.py
TRUSTED_ORIGINS = [
    "https://cdn.example.com",
    "https://admin.example.com",
]
```

This concern is included in the default `AppController`.

There is also `RequestForgeryProtection`, a legacy token-based CSRF protection. For modern browser-based applications, use `OriginProtection` instead.


#### RateLimiting

Limits the number of requests per time window. By default, rate limits apply per IP address, but you can customize the identity, scope, and reaction.

To enable rate limiting on a controller, set the `rate_limit` class attribute:

```python
from proper.units import MINUTES, HOUR

class SessionController(AppController):
    rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}
```

This allows 10 requests within 3 minutes to the `create` action. Requests that exceed the limit raise `TooManyRequests` (429).

All options:

| Option       | Description                                          | Default
| ------------ | ---------------------------------------------------- | -------
| `to`         | Max requests allowed (int, method name, or callable) | (required)
| `within`     | Time window in seconds (int, method name, or callable) | (required)
| `only`       | Action(s) to apply the limit to                      | all actions
| `exclude`    | Action(s) to exclude from the limit                  | none
| `by`         | Identity function (method name or callable)          | IP address
| `scope`      | Scope string for grouping limits                     | controller module path
| `name`       | Name to distinguish multiple limits with same scope  | `""`
| `react_with` | Method name or callable to handle exceeding limit    | raise `TooManyRequests`

Multiple rate limits on the same controller:

```python
class SessionController(AppController):
    rate_limit = [
        {
            "to": 8,
            "within": 15 * MINUTES,
            "only": "create",
            "by": lambda self: self.login_param,
            "react_with": "too_many_retries",
        },
        {"to": 50, "within": 1 * HOUR, "only": "create"},
    ]

    @property
    def login_param(self):
        return User.normalize_login(self.params.get("login") or "")

    def too_many_retries(self):
        self.response.redirect_to(
            "Session.new",
            flash="Try again in a few minutes or reset your password.",
            flash_cat="negative",
        )
```

Dynamic limits using method names:

```python
class APIController(AppController):
    rate_limit = {
        "to": "max_requests",
        "within": "time_window",
        "by": lambda self: current.user.id,
    }

    def max_requests(self):
        return 1000 if current.user.premium else 100

    def time_window(self):
        return 1 * HOUR if current.user.premium else 1 * MINUTE
```

To reset a rate limit (e.g., after a successful login):

```python
self.reset_rate_limit(self.login_param)
```

Rate limiting relies on a backing cache store. If no cache is configured, rate limiting is silently disabled.

This concern is included in the default `AppController` but does nothing unless you set the `rate_limit` class attribute.

#### CurrentLocale

Resolves the current locale for the request and assigns it to `current.locale` in a `before` callback. Wired up by the `i18n` addon — see [i18n.md](i18n.md).

Resolution order: URL param → cookie → `current.user.locale` → `app.i18n.negotiate_locale(accept_language)` → `LOCALE_DEFAULT` config.

The concern also extends `etag` to include `current.locale`, so cached responses vary by language.

#### CurrentTimezone

Resolves the current timezone and assigns it to `current.timezone` in a `before` callback. Wired up by the `i18n` addon — see [i18n.md](i18n.md).

Resolution order: URL param → cookie → `current.user.timezone` → `TIMEZONE_DEFAULT` config.

Like `CurrentLocale`, this concern extends `etag` to include `current.timezone`.

#### FormValidation

Provides the `validate_form` method that controllers register in their own `before` list. This concern is defined in your app (not in the framework) so you can customize it:

```python {title="myapp/controllers/concerns/form_validation.py"}
from proper import Concern


class FormValidation(Concern):
    def validate_form(self):
        form = getattr(self, "form", None)
        if form and form.is_invalid:
            self.redo()
```

Each generated resource controller registers three callbacks in declaration order — the load, the form build, and the validation — so each one runs in the right place:

```python
class PostController(AppController):
    before = [
        {"do": "set_post", "exclude": ["index", "new", "create"]},
        {"do": "set_form", "exclude": ["index", "show", "delete"]},
        {"do": "validate_form", "only": ["create", "update"]},
    ]
```

`validate_form` only runs on `create` and `update`. If the form is invalid it calls `self.redo()`, which sets the response body — re-rendering the form template with errors and a 422 status — halting the dispatch so the action never runs.

This concern is included in the default `AppController` so the `validate_form` method is available; the generator wires up the `before` registration on each resource controller it creates.

#### SecurityHeaders

Sets security-related response headers as an `after` callback. This concern is defined in your app (not in the framework) so you can customize it:

```python {title="myapp/controllers/concerns/security_headers.py"}
from proper import Concern

class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        self.response.headers.setdefault("X-Download-Options", "noopen")
        self.response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

## Adding More Actions

When something doesn't fit the CRUD actions in a controller, create a new controller instead of adding new methods.

**BAD:** Custom actions on an existing controller

```python {title="myapp/controllers/card_controller.py"}
from ..router import router
from .app_controller import AppController

@router.resource("cards")
class CardController(AppController):

    @router.patch("cards/:card_id/close")
    def close(self):
        """Close card"""

    @router.patch("/cards/:card_id/reopen")
    def reopen(self):
        """Reopen card"""

    @router.patch("/cards/:card_id/not-now")
    def not_now(self):
        """Postpone card"""

    ...
```

**GOOD:** New controllers for each state change

```python {title="myapp/controllers/card/closure_controller.py"}
from ...router import router
from ..concerns.card_scoped import CardScoped

@router.resource("cards/:card_id/closure", pk=None)
class ClosureController(CardScoped, AppController):

    # POST /cards/:card_id/closure
    def create(self):
        """Close a card"""

    # DELETE /cards/:card_id/closure
    def delete(self):
        """Reopen a card"""

```

```python {title="myapp/controllers/card/not_now_controller.py"}
from ...router import router
from ..concerns.card_scoped import CardScoped

@router.resource("cards/:card_id/not-now", pk=None)
class NotNowController(CardScoped, AppController):

    # POST /cards/:card_id/not-now
    def create(self):
        """Postpone a card"""

```

In these cases:

1. The card is loaded using a shared concern:

```python {title="myapp/controllers/concerns/card_scoped.py"}
from proper import Concern
from proper.errors import NotFound
from ...models import Card

class CardScoped(Concern):
    before = {"do": "set_card"}

    def set_card(self):
        card_id = self.params.get("card_id")
        if card_id:
            self.card = Card.get_or_none(card_id)
            if self.request.matched_action != "delete" and not self.card:
                raise NotFound

```

2. The new controllers do not have their own IDs, so they are mounted at "cards/:card_id/" and use the argument `pk=None`.

3. The original controller file (`card_controller.py`) and the new ones (`closure_controller.py` and `not_now_controller.py`) are moved into a subfolder `myapp/controllers/card/`. Remember to update the imports in `controllers/__init__.py`.
