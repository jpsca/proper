---
title: Controllers Overview
description: |
  Controllers receive web requests and decide what to do with them. This guide covers writing actions, reading parameters, rendering responses, redirecting, callbacks, and the tools for working with sessions, cookies, and flash messages.
number_headers: true
---

# Controllers Overview

In this guide, you will learn how controllers work and how they fit into the request cycle in your application.

- How to generate a controller, and what the generator gives you.
- How `@router.resource` maps actions to URLs.
- Access parameters passed to your controller.
- How to render templates, return JSON, and redirect.
- Store data in the cookie, the session, and one-shot flash messages.
- How `before` and `after` callbacks let you run code around your actions.
- How concerns let you share callbacks and helpers across controllers.

---

## Introduction

After the [router](/docs/routing) has matched a controller to an incoming request, the controller is responsible for processing the request and produce a response - usually an HTML page, sometimes a redirect, sometimes JSON.

Controllers live in `myapp/controllers/`, one class per file. Each class inherits from `AppController`:

```python
# myapp/controllers/card_controller.py
from ..router import router
from ..models import Card
from .app_controller import AppController


@router.resource("cards")
class CardController(AppController):
    def index(self):
        self.cards = Card.select()
```

That's a complete controller. Visit `/cards` in the browser and Proper will run `index`, set `self.cards`, render `card/index.jx`, and send the result back.

### Controller Naming Convention

Proper expects three things from a controller's name:

- **Singular** - `CardController`, not `CardsController`. Even when the URL is `/cards`.
- **Suffixed with `Controller`** - the framework relies on the suffix to derive route names and template paths.
- **Filename matches in snake_case** - `CardController` lives in `card_controller.py`.

:::tip
If you stick to the generator (next section), you don't have to think about any of this; the right names fall out automatically.
:::

### AppController

Every controller you write inherits from `AppController`, *not* directly from `Controller`. `AppController` lives in your application and is where you put behavior that should apply to every page:

```python
# myapp/controllers/app_controller.py
from proper import Controller
from proper.concerns import OriginProtection, Pagination, RateLimiting

from .concerns.form_validation import FormValidation
from .concerns.security_headers import SecurityHeaders


class AppController(
    OriginProtection,
    Pagination,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
    Controller,
):
    pass
```

The mixins it inherits from are *concerns* - small classes that bundle behavior. We'll come back to them in [Concerns](#concerns); for now, just know that the five shipped here give you CSRF protection, pagination, rate limiting, form validation, and sensible security headers without you having to wire them up.

---

## Generating a Controller

You almost never write a controller from a blank file. Use the generator - it creates the controller, the form, the views, and (for resources) the model and its migration, all wired up correctly.

### With a Model: `proper g resource`

If the controller is going to manage a database-backed thing - a card, a post, a user - generate a *resource*:

```bash
proper g resource Card title:str body:text
```

This produces:

- `myapp/models/card.py` - the model.
- `migrations/NNN_create_cards.py` - the migration that creates the table.
- `myapp/forms/card.py` - the form, with one field per model field.
- `myapp/controllers/card_controller.py` - the controller, with all seven CRUD actions.
- `myapp/views/card/` - `index.jx`, `show.jx`, `new.jx`, `edit.jx`, and `form.jx`.

Run `proper g resource --help` to see all the options.

### Without a Model: `proper g controller`

If the controller doesn't have a model behind it - a `DashboardController`, a `HealthcheckController` - generate just a controller:

```bash
proper g controller Dashboard
```

This produces the controller, an empty form (you can delete it if you don't need one), and the view files.

### If You Only Need a Model

If you have a model but no new controller - say, a `Tag` model that's only ever managed through the admin UI - use the model generator instead:

```bash
proper g model Tag name:str
```

:::note | Namespaced controllers
You can scope a controller under a subfolder with `--namespace=admin`. The generator creates `controllers/admin/post_controller.py`, mounts its routes under `/admin/...`, and gives them prefixed names like `Admin:Post.show`. The [Routing guide](/docs/routing) covers the details.
:::

:::tip | Why the generator matters
The generator wires up `__init__.py` imports, picks the right route names, creates the migration, and lays files out so Proper's conventions hold. Hand-rolling a controller is possible, but you'll spend more time fixing imports than writing code.
:::

---

## The Shape of a Generated Controller

Let's look at what `proper g resource Card title:str body:text` produces, simplified slightly:

```python
# myapp/controllers/card_controller.py
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
        if self.card:
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

There's a lot in there, but the pattern repeats across every resource you'll ever generate. Let's walk through it.

:::note
You can tell the generators that you only want _some_ of the actions, e.g.:

`proper g controller Post --only=index,show`

or all of the action _except some_

`proper g controller Post --exclude=new,create`
:::

### CRUD

`index`, `new`, `create`, `show`, `edit`, `update`, and `delete` are the seven CRUD actions Proper recognizes. Together they cover every operation a user can perform on a collection of records:

| Action   | Purpose                                       |
| -------- | --------------------------------------------- |
| `index`  | List all records.                             |
| `new`    | Show a blank form for creating a record.      |
| `create` | Receive that form and create the record.      |
| `show`   | Display a single record.                      |
| `edit`   | Show a form pre-filled for editing a record.  |
| `update` | Receive that form and save the changes.       |
| `delete` | Remove a record.                              |

The split between `new` / `create` and `edit` / `update` mirrors the two-step nature of HTML forms: one URL renders the form, another receives it. `new` and `edit` are GET requests; `create`, `update`, and `delete` change data.

### The Setup Callbacks

Look at the top of the class:

```python
before = [
    {"do": "set_card", "exclude": ["index", "new", "create"]},
    {"do": "set_form", "exclude": ["index", "show", "delete"]},
    {"do": "validate_form", "only": ["create", "update"]},
]
```

Three `before` callbacks, listed in the order they run. Each one narrows its scope with `only` or `exclude` - declarations Proper reads to decide which actions the callback applies to.

`set_card` runs for `show`, `edit`, `update`, and `delete` - every action that operates on an existing record. It loads the card by ID and stashes it on `self.card`:

```python
def set_card(self):
    card_id = self.params.get("card_id", "")
    self.card = Card.get_or_none(id=int(card_id))
    if self.request.matched_action != "delete" and not self.card:
        raise NotFound
```

The `delete` exception is deliberate: deleting the same card twice (someone double-clicks the button) shouldn't 404 - we want it to silently succeed.

`set_form` runs for `new`, `edit`, `create`, and `update` - every action that renders or processes a form. It builds the form with the request params, pre-filled from the loaded card if there is one:

```python
def set_form(self):
    obj = getattr(self, "card", None)
    self.form = CardForm(self.params, object=obj)
```

For `new` and `create`, no card has been loaded (`set_card` was excluded), so `obj` is `None` and the form starts empty. For `edit` and `update`, the form is pre-filled from `self.card`.

### Form Validation

The third callback, `validate_form`, runs only on `create` and `update`. It comes from the `FormValidation` concern your `AppController` mixes in:

```python
# myapp/controllers/concerns/form_validation.py
def validate_form(self):
    form = getattr(self, "form", None)
    if form and form.is_invalid:
        self.redo()
```

If the form is invalid, `self.redo()` re-renders the `new` or `edit` template with a `422 Unprocessable Entity` status, and the action never runs. If the form is valid, control passes on to the action.

### The Action Bodies

Once the three setup callbacks have done their work, the action methods are tiny:

- `index` queries for cards and assigns them to `self.cards`.
- `show`, `new`, and `edit` are empty - they just render their templates with whatever the callbacks set up.
- `create` calls `self.form.save()` to build and INSERT the model, then redirects with a flash message.
- `update` is almost identical - `self.form.save()` applies the changes to the card that `set_card` loaded and UPDATEs the row.
- `delete` removes the row and redirects to the index.

This is the shape of nearly every controller you'll write: small actions, with the heavy lifting (loading, form-building, validation) factored into callbacks above them.

:::note
Callbacks set things up; actions decide what happens; templates render the result.
:::

---

## `@router.resource`

The `@router.resource` decorator does most of the work of mounting a controller. It takes one positional argument and a few keyword options that adjust the URLs it generates.

### The Path

The first argument is the URL prefix the resource lives under:

```python
@router.resource("cards")
class CardController(AppController):
    ...
```

It's almost always the plural form of the controller's name, lowercased. Multi-word resources are kebab-cased: `@router.resource("user-profiles")`.

### The ID Parameter (`pk=`)

By default, Proper builds the ID parameter by taking the controller's name (minus the `Controller` suffix), converting it to snake_case, and appending `_id`:

- `CardController` -> `:card_id`
- `UserPhotoController` -> `:user_photo_id`

Override it with the `pk` argument when you need a different name. Whatever you pass becomes the parameter name verbatim - Proper won't append `_id` for you:

```python
@router.resource("cards", pk="object")
```

Now `show`'s URL is `/cards/:object`, and inside the controller you read `self.params["object"]`. If you want an `_id` suffix, include it yourself: `pk="object_id"`.

### Singular Resources (`pk=None`)

Some resources don't have an ID at all - the current user's profile, the dashboard, the site settings. There's only ever one. Pass `pk=None` to drop the ID parameter entirely:

```python
@router.resource("profile", pk=None)
class ProfileController(AppController):
    ...
```

The URL table changes:

| HTTP   | PATH            | ACTION   |
| ------ | --------------- | -------- |
| GET    | /profile/new    | new      |
| POST   | /profile        | create   |
| GET    | /profile        | show     |
| GET    | /profile/edit   | edit     |
| PATCH  | /profile        | update   |
| PUT    | /profile        | update   |
| DELETE | /profile        | delete   |

`index` is gone - without an ID, there's no distinction between "the list" and "the single item," so listing doesn't make sense. The `:profile_id` segment is removed from every other path as well.

:::note | Scoped routers
For namespaced controllers, you'll see `@admin_router.resource(...)` instead of `@router.resource(...)`. Same arguments, same behavior - the scoped router just prepends the namespace prefix to every URL it generates. See the [Routing guide](/docs/routing) for more.
:::

---

## Where the URLs Come From

Once you've mounted a controller with `@router.resource("cards")`, the seven CRUD actions become seven URLs:

HTTP     | PATH                 | ACTION   | USED FOR
-------- | -------------------- | -------- | -------------------------------
GET      | /cards               | index    | a list of all cards
GET      | /cards/new           | new      | form for creating a new card
POST     | /cards               | create   | create a new card
GET      | /cards/:card_id      | show     | show a specific card
GET      | /cards/:card_id/edit | edit     | form for editing a specific card
PATCH    | /cards/:card_id      | update   | update a specific card
PUT      | /cards/:card_id      | update   | replace a specific card
DELETE   | /cards/:card_id      | delete   | delete a specific card

You don't write these URLs yourself; the router builds them from the actions you define on the class.

:::warning | Missing methods, missing routes
If one of the seven actions is *not* defined on the class, its URL is *not* created. A controller with only `index` and `show` will have routes for `GET /cards` and `GET /cards/:card_id`, and that's it. There's no 405 for `POST /cards` - the route simply doesn't exist.

This is intentional: the routes mirror the controller. To remove an action from the public surface, delete the method.

One special case: if `new` is defined but `index` (or `show`, for `pk=None` resources) is not, the `new` action is mounted at `/cards` instead of `/cards/new`. The root path is free, so it's used.
:::

The [Routing guide](/docs/routing) goes deeper - manually-defined routes with `@router.get`, `@router.post`, etc., named routes, route inspection, and scoped routers.

---

## Parameters

Data sent by the incoming request is available in your controller via `self.params`. It's a `MultiDict` that merges three sources:

1. **Query string parameters** - from the URL (e.g., `?status=activated`).
2. **Form body parameters** - submitted from an HTML form, including file uploads.
3. **Route parameters** - extracted from the URL path (e.g., `:card_id`).

If the same key appears in more than one source, route parameters win, then the form, then the query string. So `:card_id` from the URL will always override a `card_id` smuggled in via the query string.

```python
@router.resource("clients")
class ClientController(AppController):

    # GET /clients?status=activated
    def index(self):
        if self.params.get("status") == "activated":
            self.clients = Client.get_activated()
        else:
            self.clients = Client.get_inactivated()

    # POST /clients
    def create(self):
        client = self.form.save()
        self.response.redirect_to("Client.show", client, flash="Client was created")
```

### Reading Parameters

Three methods cover almost every case:

```python
self.params.get("key")          # value, or None if missing
self.params["key"]               # value, or KeyError if missing
self.params.getall("key")       # list of all values for the key
```

Because `self.params` is a `MultiDict`, `self.params["key"]` returns the *last* value when the same key was sent multiple times. That's almost always what you want for plain text fields, but it's the wrong choice for a multi-select or a checkbox group:

```html
<input type="checkbox" name="tags" value="python">
<input type="checkbox" name="tags" value="javascript">
<input type="checkbox" name="tags" value="ruby">
```

If the user ticks all three, `self.params["tags"]` returns only `"ruby"`. Use `self.params.getall("tags")` to get the full list.

### Sources Individually

When you need to know *where* a parameter came from - for example, to reject a value that should only ever arrive via a route segment - the three sources are also available individually:

```python
self.request.query              # query string only (MultiDict)
self.request.form               # POST body only (MultiDict)
self.request.matched_params     # route params only (dict)
```

Reach for `self.params` first; the merged view is what you almost always want.

### File Uploads

Uploaded files arrive in `self.request.form` alongside the regular form fields. Each file is an object with a filename, a content type, and a `.read()` / `.save()` API:

```python
def create(self):
    upload = self.request.form.get("avatar")
    if upload:
        upload.save(f"/var/uploads/{upload.filename}")
```

For attaching files to model records, see the [File Storage](/docs/storage) guide - it gives you S3 support, content-type validation, and image variants without you having to write the plumbing.

### Route Defaults

Routes can attach default values that flow into the controller as `self.defaults`:

```python
# in the router
@router.get(":slug", defaults={"sidebar": True})
def show(self):
    ...

# in the controller
self.defaults["sidebar"]   # True
```

`self.defaults` is separate from `self.params` on purpose - defaults are set by *you* when wiring the route, and shouldn't be confused with values the user submitted.

---

## Rendering Responses

Once an action has done its work, Proper needs to turn the result into bytes the browser can understand. Most of the time that means rendering a template, but you can also return JSON, plain text, or a string straight from the action.

### Implicit Rendering

If an action returns `None` and doesn't set the response body, Proper picks the right template for you. The simplest action is one that does nothing:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    # automatically renders card/show.jx
```

The lookup walks the controller's class hierarchy and the request's `Accept` header to find the best match - so an admin controller subclassing a public one inherits its template folder as a fallback, and a request for `application/json` can be handled by a `.json.jx` template if one exists. The [Jx Components and Layouts guide](/docs/jx_components) covers the full algorithm; for most pages, you don't have to think about it - the file at `<controller>/<action>.jx` is what gets rendered.

### Template Variables

Every instance attribute you set on the controller is passed to the template as a variable:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.related = (
        Card.select()
        .where(Card.category == self.card.category)
        .limit(5)
    )
    # {{ card }} and {{ related }} are now available in show.jx
```

There's no manual context dictionary to assemble - if you wrote `self.foo = ...`, the template can use `{{ foo }}`.

### Explicit Rendering

When you need a different template, or want to set a custom status, call `self.render()`:

```python
def show(self):
    self.card = Card.get_or_none(self.params["card_id"])
    if not self.card:
        return self.render("card/not_found.jx", status=404)
```

The path you pass goes straight to the template catalog - the prefix chain and format negotiation that implicit rendering does are skipped.

### JSON

Pass `json=` to render a value as JSON:

```python
def show(self):
    card = Card.get_by_id(self.params["card_id"])
    return self.render(json={"id": card.id, "title": card.title})
```

This sets `Content-Type: application/json` and serializes the value with a custom encoder that handles `datetime` objects.

For full API patterns - content negotiation between HTML and JSON, JSON-only controllers, JSON error responses - see the [Building API-only Applications](/docs/api) guide.

### Plain Text

Pass `text=` for `text/plain` responses:

```python
def healthcheck(self):
    return self.render(text="ok")
```

### Returning a String Directly

If an action returns any non-`None` value, that value becomes the response body verbatim. You can set the content type yourself before returning:

```python
def healthcheck(self):
    self.response.content_type = "text/plain"
    return "ok"
```

This works for any content type (`text/plain`, `text/csv`, `application/xml`, ...). For the common cases `self.render(text=...)` and `self.render(json=...)` are easier, since they set the content type for you.

### Custom Status Codes

Every render mode accepts a `status` argument:

```python
return self.render(json={"id": card.id}, status=201)
return self.render(text="created", status=201)
```

You can also set the status on the response object directly, which is handy when a callback decides what status to use:

```python
from proper import status

self.response.status = status.created
```

Status codes are available as integers under `proper.status` (e.g., `proper.status.unprocessable` is `422`).

---

## Redirecting

After a successful `create`, `update`, or `delete`, you almost always want to send the user somewhere else - typically the page that shows what they just changed. Use `self.response.redirect_to()`:

```python
# named route + the object (preferred)
self.response.redirect_to("Card.show", card)

# named route with an explicit ID
self.response.redirect_to("Card.show", card_id=card.id)

# absolute URL
self.response.redirect_to("/dashboard")

# external URL
self.response.redirect_to("https://example.com")
```

Redirects default to `303 See Other`, which is the right status after a `POST`.

:::note | Why 303, not 302
Both work in practice - every modern browser treats a 302 after a POST as if it were 303. The reason Proper picks 303 is intent: 303 explicitly says "the response is at another URL, fetch it with GET regardless of the original method," which is exactly the post-redirect-get pattern you want after a successful `create` or `update`. 302 was historically ambiguous about whether the method should change between the original request and the redirect.
:::

Override the default for permanent redirects or other cases:

```python
from proper import status

self.response.redirect_to("/new-location", status=status.moved_permanently)
```

:::tip | Pass the object, not its ID
When a route takes an ID, prefer `redirect_to("Card.show", card)` over `redirect_to("Card.show", card_id=card.id)`. Both work, but passing the object reads better and survives renames of the route's ID parameter.
:::

### Generating URLs: `url_for`

`url_for` is the same naming system as `redirect_to`, used wherever you need a URL string instead of an HTTP redirect. In Python:

```python
app.url_for("Card.index")          # /cards
app.url_for("Card.show", card)     # /cards/42
```

In a template:

```html
<a href="{{ url_for('Card.show', card) }}">View card</a>
```

Named routes follow a `Controller.action` convention. Namespaced controllers prefix the namespace in PascalCase: `Admin:Post.show`. The [Routing guide](/docs/routing) covers the full naming rules and how to inspect the routes your app has.

### Flash Messages

A flash message is a one-shot bit of text that survives a single redirect - "Card was created", "Try again in a few minutes". Set one as part of a redirect:

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

`flash_cat` defaults to `"positive"`. Common categories are `"positive"`, `"negative"`, `"warning"`, and `"info"` - your layout decides how each one looks.

You can also set a flash message without redirecting, useful when an action renders a page itself but still wants to acknowledge something:

```python
self.response.flash.message("positive", "Settings saved")
```

In your templates, flash messages are available as a list of `(category, message)` tuples; the layout that ships with the generator already renders them.

---

## Sessions

The session is a small bag of data that follows the user across requests. It's stored in a signed cookie, so users can't tamper with it - which is why it's safe to use for things like the current user's ID.

Read from `self.request.session`, write to `self.response.session`. The session is a `DotDict`, so dict-style and attribute-style access both work:

```python
# read
value = self.request.session.get("key")
value = self.request.session.key

# write
self.response.session["key"] = value
self.response.session.key = value
```

Proper compares the request and response sessions at the end of every request, and only writes a new cookie if anything changed - so reads alone don't cost you a cookie roundtrip.

:::tip | Why two sessions?
Splitting reads and writes makes it explicit which values were "what we got from the user" and which are "what we're about to send back." Without that split, a callback that *reads* a value to make a decision would look identical to one that *writes* a value to change state, and a misplaced assignment could silently overwrite the user's session.
:::

---

## Cookies

The session is the most common reason to set a cookie, but you can set arbitrary cookies too - language preferences, theme choices, dismissed banners.

### Plain Cookies

```python
# read
theme = self.request.get_cookie("theme", default="light")

# write
self.response.set_cookie("theme", "dark", max_age=31536000)

# delete
self.response.unset_cookie("theme")
```

Sensible defaults are baked in: cookies are scoped to `path="/"`, marked `samesite="Lax"`, and last only for the browser session unless you pass `max_age`. Common options:

Option     | Purpose
---------- | --------------------------------------------------------------
`max_age`  | Lifetime in seconds. Omit for a session-only cookie.
`path`     | URL path the cookie applies to. Defaults to `"/"`.
`domain`   | Subdomain restriction. Defaults to the current host.
`secure`   | Only sent over HTTPS. Recommended for anything sensitive.
`httponly` | Hidden from JavaScript. Recommended for anything sensitive.
`samesite` | `"Lax"` (default), `"Strict"`, or `"None"`.

### Signed Cookies

A plain cookie is data the user can read *and edit* - they can open DevTools and rewrite the value to anything they want. A signed cookie is the same data plus a cryptographic signature; if the user edits it, the signature stops matching and Proper rejects it.

Reach for signed cookies whenever the value is something the user shouldn't be able to forge - a CSRF token, a "remember me" token, a stored user ID:

```python
# write
self.response.set_signed_cookie("_auth", user.id, max_age=2592000, httponly=True)

# read - returns None if the signature doesn't match
user_id = self.request.get_signed_cookie("_auth", max_age=2592000)
```

The `max_age` on the read side isn't just a hint: signed cookies older than `max_age` are also rejected, even if the signature is still valid. This protects against an attacker reusing a stolen-but-old cookie.

:::warning | Don't put secrets in cookies, signed or not
Signed cookies prevent *tampering*, not *reading*. Anyone with browser access can still see what's in them. Store IDs and references in cookies; keep the actual sensitive data on the server.
:::

---

## Request and Response Objects

Most of what you read from `self.request` and write to `self.response` has come up in the previous sections - parameters, sessions, cookies, status, content type. The objects have a handful more attributes that come up less often but are worth knowing.

### Useful on `self.request`

```python
self.request.method            # "GET", "POST", "PATCH", ...
self.request.path              # "/cards/42"
self.request.url               # full URL including scheme and host
self.request.headers           # incoming headers, MultiDict with lowercase keys
self.request.format            # "html", "json", ... (from the Accept header)
self.request.is_xhr            # True if X-Requested-With: XMLHttpRequest
self.request.remote_ip         # client IP address
self.request.matched_action    # the action name the router matched ("show", "create", ...)
```

### Useful on `self.response`

```python
self.response.headers["X-Custom"] = "value"
self.response.set_cache_control("max-age=3600", "public")
self.response.send_file(
    "/path/to/report.pdf",
    as_attachment=True,
    download_name="Q4-Report.pdf",
)
```

`send_file` is the one to reach for when an action's job is to return a file from disk - a generated PDF, an export, a rendered chart. It sets the content type, the right headers, and (with `as_attachment=True`) prompts the browser to download instead of display.

---

## Before and After Callbacks

A callback is a method that runs automatically around your action - either before it (`before`) or after it (`after`). You've already seen one: the generated controller's `set_card` is a `before` callback that loads the card and builds the form on every action that needs them.

The motivation is straightforward: most controllers end up with the same setup at the top of every action. Loading a record, checking permissions, setting response headers. Callbacks let you write that setup once and have it run automatically.

### The `before` Callback

Declare a `before` callback by assigning a dict to the class attribute `before`:

```python
class CardController(AppController):
    before = {"do": "set_card", "exclude": ["index", "new", "create"]}

    def set_card(self):
        card_id = self.params.get("card_id", "")
        self.card = Card.get_or_none(id=int(card_id))
        if self.request.matched_action != "delete" and not self.card:
            raise NotFound

    def show(self):
        # self.card is already loaded
        pass
```

The dict has three keys:

Key       | Meaning
--------- | --------------------------------------------------
`do`      | The name of the method to call. Required.
`only`    | A list of action names to run on. Optional.
`exclude` | A list of action names to skip. Optional.

If neither `only` nor `exclude` is given, the callback runs for every action.

### Multiple Callbacks

Pass a list of dicts to declare more than one:

```python
class CardController(AppController):
    before = [
        {"do": "set_card", "exclude": ["index"]},
        {"do": "ensure_editor", "only": ["edit", "update", "delete"]},
    ]

    def set_card(self):
        ...

    def ensure_editor(self):
        if not current.user.can_edit(self.card):
            raise Forbidden
```

Callbacks run in the order you list them. `set_card` runs first, then `ensure_editor` - which depends on `self.card` being set.

### Halting

If a `before` callback sets the response body - by calling `self.render(...)`, `self.response.redirect_to(...)`, or assigning `self.response.body` directly - the action never runs. Subsequent `before` callbacks don't run either. The framework treats it as "this callback already produced a response; we're done here."

```python
class AdminController(AppController):
    before = {"do": "require_admin"}

    def require_admin(self):
        if not current.user.is_admin:
            self.response.redirect_to("Home.show", flash="Admin only.")
            # action never runs
```

Raising an HTTP error class (`NotFound`, `Forbidden`, ...) also halts the dispatch, but via the error-handler path rather than the response body. Both stop the action from running.

:::warning | A halted `before` is logged
If a `before` callback halts the action, the framework logs it at DEBUG level. If something is mysteriously not running, check the logs for "halted by before callback".
:::

### The `after` Callback

`after` callbacks run after the action has produced a response. They have access to the response that's about to be sent, which makes them useful for setting headers or post-processing the body:

```python
class CardController(AppController):
    after = {"do": "set_no_cache", "only": ["edit"]}

    def set_no_cache(self):
        self.response.set_cache_control("no-store")
```

Same dict shape as `before`: `do`, `only`, `exclude`. Same support for a list of dicts when you have several.

:::note | `after` doesn't run after errors
`after` callbacks only run when the action completed successfully. If the action (or a `before` callback) raised an exception, the `after` callbacks are skipped and the framework's error handler takes over. So don't use `after` for cleanup that has to happen unconditionally - use a `try`/`finally` inside the action, or a concern method called explicitly.
:::

### Inheritance

Callbacks declared on `AppController` (or any parent class) run for every controller that inherits from it. Order matters and is one of the most-asked questions about callbacks in any framework, so:

- **`before`** callbacks run **outer-first**: parent class → child class.
- **`after`** callbacks run **inner-first**: child class → parent class.

The pattern is "child wraps parent." For a single request:

```
parent.before  →  child.before  →  action  →  child.after  →  parent.after
```

Each class's own `before`/`after` is collected independently from its own class body along the inheritance chain, so a child that declares `before` does not override the parent's - both run.

This means a `before` callback on `AppController` always runs before any `before` callback on a child controller. The classic example is requiring login:

```python
class AppController(Controller):
    before = {"do": "require_login"}

    def require_login(self):
        if not current.user:
            self.response.redirect_to("Session.new")


class CardController(AppController):
    before = {"do": "set_card", "exclude": ["index"]}

    def set_card(self):
        # safe to query the DB here - require_login already ran
        self.card = Card.get_or_none(...)
```

A logged-out request to `GET /cards/42` runs `require_login` first. It redirects to the login page and sets the response body, halting the dispatch - so `set_card` never runs and the database is never queried.

This is the right order: cheap, broad checks first; expensive, specific work later. Concerns mixed into `AppController` (origin protection, rate limiting, security headers) are also "outer" relative to your child controllers, and run in that same order.

---

## Concerns

A concern is a class that bundles callbacks and helper methods so you can share them across controllers. They're plain Python mixins, but they inherit from `proper.Concern` rather than `Controller`, which lets the framework distinguish "behavior to mix in" from "controllers to mount."

You've already met five of them. Open `myapp/controllers/app_controller.py` and you'll see:

```python
class AppController(
    OriginProtection,
    Pagination,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
    Controller,
):
    pass
```

Those five ship with every Proper application. Three come from the framework (`OriginProtection`, `Pagination`, `RateLimiting`); two live in your app under `myapp/controllers/concerns/` so you can edit them (`FormValidation`, `SecurityHeaders`).

### `OriginProtection`

Modern CSRF protection. It verifies that state-changing requests (POST, PATCH, PUT, DELETE) come from a trusted origin, using the browser's `Sec-Fetch-Site` and `Origin` headers - no tokens needed. Safe methods (GET, HEAD, OPTIONS, QUERY) are skipped; cross-origin state changes raise `403 Forbidden`.

To allow requests from other domains (an admin subdomain, a CDN), list them in your config:

```python
# config/main.py
TRUSTED_ORIGINS = [
    "https://cdn.example.com",
    "https://admin.example.com",
]
```

The full algorithm is covered in the [Security guide](/docs/security).

### `Pagination`

Paginates a query and hands the current page to your templates. It's a port of Basecamp's [geared_pagination](https://github.com/basecamp/geared_pagination), and it brings that library's signature trick: **geared page sizes**. Instead of a fixed `per_page`, you give a progression like `[15, 30, 50, 100]` - page 1 returns 15 records, page 2 returns 30, page 3 returns 50, and every page from 4 on returns 100. The first screen loads fast; later pages arrive in bigger batches. It's a natural fit for infinite scroll.

Call `paginate_for` from an action. It reads the `page` query parameter, sets `self.page`, and returns the records for that page:

```python
@router.resource("posts")
class PostController(AppController):
    def index(self):
        self.posts = self.paginate_for(
            Post.select().order_by(Post.created_at.desc()),
            per_page=[15, 30, 50, 100],
        )
```

`self.page` is a `Page` object the template can walk:

```html
{% for post in posts %}
  <article>{{ post.title }}</article>
{% endfor %}

<p>Page {{ page.number }} of {{ page.recordset.page_count }}
   ({{ page.recordset.records_count }} posts in total).</p>

{% if page.is_last %}
  No more pages.
{% else %}
  <a href="{{ url_for('Post.index', page=page.next_param) }}">Next page</a>
{% endif %}
```

`page.next_param` is what you pass back as the `page` parameter to fetch the following page - a plain page number here, or `None` once you reach the end.

**Cursor (keyset) paging.** Offset paging slows down on deep pages (the database still scans every skipped row) and can skip or repeat records when rows shift under you. Pass `ordered_by` to switch to cursor paging, which avoids both:

```python
self.posts = self.paginate_for(
    Post.select(),
    ordered_by=[(Post.created_at, "desc"), (Post.id, "desc")],
)
```

The last column must be unique (usually the primary key) so the order is total and no row is skipped or repeated. Page sizes stay geared - the page number rides inside the cursor. The template is unchanged, except `page.next_param` is now an opaque token that Proper reads back on the next request (you'd typically drop the page-count line, since computing it would need the very `COUNT` that cursor paging skips). Cursor paging is *count-free*: each page fetches one extra row to detect whether another page follows.

:::note | JSON responses get pagination headers
On a JSON response the concern also sets `X-Total-Count` (offset mode only - cursor mode stays count-free) and a `Link: rel="next"` header pointing at the next page, dropped on the last page. And `self.page.cache_key` is folded into the response `etag`, so conditional requests work without extra wiring.
:::

### `RateLimiting`

Lets you cap how many requests a controller will accept in a time window. The concern is wired up but does nothing until you set `rate_limit` on a controller:

```python
from proper.units import MINUTES

class SessionController(AppController):
    rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}
```

This allows ten POSTs to `Session.create` per IP per three minutes. Anything beyond raises `429 Too Many Requests`. The concern can identify clients by something other than IP, run different limits on different actions, and hand off to a custom reaction method instead of raising - the [Security guide](/docs/security) covers the full surface.

Rate limiting needs a configured cache store. If no cache is configured, the limits are silently ignored.

### `FormValidation`

Provides the `validate_form` method that the generator wires into every resource controller's `before` list. It checks `self.form` and, if invalid, calls `self.redo()` - which re-renders the form template with a `422 Unprocessable Entity` status, halting the dispatch.

The concern lives in your app at `myapp/controllers/concerns/form_validation.py`, so you can change it. The default does the right thing for HTML forms; for JSON APIs you'll typically skip it and validate inline (see the [API-only Applications guide](/docs/api)).

### `SecurityHeaders`

Sets a small set of safe-by-default response headers via an `after` callback. The default lives at `myapp/controllers/concerns/security_headers.py`:

```python
class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        ...
```

Edit it to fit your application's threat model - adding a Content Security Policy, tightening the referrer policy, or whatever else your security review asks for.

### Writing Your Own

A concern is the right place to put behavior that more than one controller needs. The convention is one concern per file under `myapp/controllers/concerns/`:

```python
# myapp/controllers/concerns/team_scoped.py
from proper import Concern
from proper.errors import NotFound

from ...models import Team


class TeamScoped(Concern):
    before = {"do": "set_team"}

    def set_team(self):
        team_id = self.params.get("team_id")
        self.team = Team.get_or_none(id=team_id)
        if not self.team:
            raise NotFound
```

Mix it into any controller that operates inside a team:

```python
class ProjectController(TeamScoped, AppController):
    def index(self):
        # self.team was loaded by the concern
        self.projects = self.team.projects
```

A few rules of thumb:

- **List concerns before `AppController`** when mixing them into individual controllers (`TeamScoped, AppController`). Python's MRO uses left-to-right order, and listing the concern first makes its callbacks run closer to the child than `AppController`'s do. Concretely for `before` (which runs in reversed-MRO order, so the left-most class runs last): `AppController`'s `before` runs first, then `TeamScoped`'s.
- **Keep concerns focused.** "Loads a team," "checks editor access," "tracks page views" - one job each. If a concern grows past 30 or 40 lines, it's probably doing too much.
- **Concerns aren't a way to share state.** They're a way to share *behavior*. If two controllers need the same data, that's usually a model concern (covered in the [Models guide](/docs/models)) or a helper, not a controller concern.

---
