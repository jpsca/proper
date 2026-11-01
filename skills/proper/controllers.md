---
title: Controllers
description: Controller fundamentals: CRUD and state-change resources, the generated controller, parameters, sessions
last_verified: 2026-10-31
sources:
  - src/proper/controller
  - src/proper/pipeline.py
  - src/proper/_blueprints/controller
  - src/proper/generators
---

# Controllers

Controllers receive the request and produce the response. This file covers how a controller is defined and what the generated one does. Responses are in [rendering.md](rendering.md), callbacks and concerns in [concerns.md](concerns.md), admin-style namespaces in [namespacing.md](namespacing.md).

## Table of Contents

- [Introduction](#introduction)
- [Adding a controller](#adding-a-controller)
- [The Core Principle: CRUD](#the-core-principle-crud)
- [The Generated Controller](#the-generated-controller)
- [Parameters](#parameters)
- [Sessions](#sessions)
- [HTTP Method Override](#http-method-override)


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
from proper.concerns import OriginProtection, Pagination, RateLimiting

from .concerns.security_headers import SecurityHeaders


class AppController(
    OriginProtection,
    Pagination,
    RateLimiting,
    SecurityHeaders,
    Controller,
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

In both cases, in addition to the controller file, a form, the views and a test skeleton (`tests/controllers/test_<name>.py`) are generated as well. Edit them as needed.

`proper g controller` uses the model of the same name if `models/__init__.py` already imports one. Otherwise the generated code has no model: the actions are stubs with `TODO` comments. In both cases the views and redirects only use the actions that were generated (`--only` / `--exclude`).

Read the output of `proper g resource --help`, `proper g controller --help`, and  `proper g model --help` to see all the options.

If you are only adding a model, use the model generator `proper g model NAME ...` instead.


The attribute syntax of the generators is in [generators.md](generators.md). A separate controller for the same resource (an admin interface) is in [namespacing.md](namespacing.md).


## The Core Principle: CRUD

The `router.resource` class decorator is the most common method to mount a controller in the right URLs. This decorator maps the `index`, `new`, `create`, `show`, `edit`, `update`, and `delete` methods of the controller class (if they exist) to the matching CRUD routes:

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

**Warning:** If one of those methods doesn't exist in the controller class, its URL is not created.


### Beyond records: state changes are resources too

In Proper, **every state change is a resource.** You don't add verbs to a controller: you create a controller for the thing that changes.

Records are the common case, not the only one. A card can be closed and reopened. A user can be suspended and restored. A subscription can be cancelled and resumed. Each of those is *also* a resource — a thing you `POST` to make happen and `DELETE` to undo — even though there's no new row in a table.

The mistake is to bolt the verb onto the existing controller with a custom route:

**BAD:** custom verbs on the parent controller

```python {title="myapp/controllers/card_controller.py"}
@router.resource("cards")
class CardController(AppController):

    @router.patch("cards/:card_id/close")
    def close(self): ...

    @router.patch("cards/:card_id/reopen")
    def reopen(self): ...

    @router.patch("cards/:card_id/not-now")
    def not_now(self): ...
```

This bloats the controller with every new transition, invents an ad-hoc URL and route name per verb, and breaks the `Controller.action` naming convention.

**GOOD:** one controller per state change, mounted under the parent with `pk=None`

```python {title="myapp/controllers/card/closure_controller.py"}
from proper.errors import NotFound

from ...router import router
from ..app_controller import AppController
from ..concerns.card_scoped import CardScoped


@router.resource("cards/:card_id/closure", pk=None)
class ClosureController(CardScoped, AppController):

    # POST /cards/:card_id/closure
    def create(self):
        self.load_card()
        if not self.card:
            raise NotFound
        self.card.close()
        self.response.redirect_to("Card.show", self.card, flash="Card closed")

    # DELETE /cards/:card_id/closure
    def delete(self):
        self.load_card()
        if not self.card:
            raise NotFound
        self.card.reopen()
        self.response.redirect_to("Card.show", self.card, flash="Card reopened")
```

```python {title="myapp/controllers/card/not_now_controller.py"}
@router.resource("cards/:card_id/not-now", pk=None)
class NotNowController(CardScoped, AppController):

    # POST /cards/:card_id/not-now
    def create(self):
        self.load_card()
        if not self.card:
            raise NotFound
        self.card.postpone()
        self.response.redirect_to("Card.show", self.card)
```

`pk=None` drops the trailing ID — there's only ever one closure for a card, so `/cards/:card_id/closure` is the whole address. Route names follow the standard convention (`Closure.create`, `Closure.delete`, `NotNow.create`), and each controller stays small: a new state change is a new file, not a new method.

The lookup of the parent record lives in a shared concern so every child controller gets it for free:

```python {title="myapp/controllers/concerns/card_scoped.py"}
from proper import Concern
from ...models import Card


class CardScoped(Concern):
    def load_card(self):
        card_id = self.params.get("card_id", "")
        self.card = Card.find(int(card_id)) if card_id.isdigit() else None
```

The concern only provides the loader: `load_card()` sets `self.card` to the card in the URL, or to `None`. Each action calls it and raises `NotFound` if the card is missing, so the load stays visible in the action.

**ALWAYS** scaffold a state-change controller with a `PARENT/CHILD` name:

```bash
proper g controller card/closure
proper g controller card/not_now --only=create
```

This generates the `pk=None` controller with `create`/`delete` stubs under `controllers/card/`, creates the `CardScoped` concern (if it doesn't exist yet), and wires the import into `controllers/__init__.py`. No form or views are generated, since a state change redirects rather than rendering a form; a test skeleton `tests/controllers/test_<child>.py` is. Group the parent and its children under the `controllers/card/` subfolder; the original `card_controller.py` can stay where it is or move to `card/main_controller.py`.


### ID parameter

The `:card_id` parameter is the snake-cased controller name (after removing the "Controller" suffix) plus `_id`. No singularization is applied (`CardsController` would give `:cards_id`): name controllers in singular.

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

When a controller defines `new` but not the action of the root path (`index`, or `show` for `pk=None`), `new` is mounted at the root (`/signup` instead of `/signup/new`): handy for sign-up style resources where the form is the landing page.


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

**Warning:** This should be used only for exceptional cases, such as the home page.


## The Generated Controller

When you run `proper g resource Card title:str body:text`, Proper generates a controller with the full CRUD pattern. Here's what it looks like (simplified):

```python {title="myapp/controllers/card_controller.py"}
from proper.errors import NotFound

from myapp.forms.card import CardForm
from myapp.models import Card
from myapp.router import router
from .app_controller import AppController


@router.resource("cards")
class CardController(AppController):

    def index(self):
        self.cards = Card.select()

    def show(self):
        self.load_card()
        if not self.card:
            raise NotFound

    def new(self):
        self.form = CardForm(self.params)

    def create(self):
        self.form = CardForm(self.params)
        if self.form.is_invalid:
            return self.redo()

        self.form.save()
        self.response.redirect_to("Card.index", flash="Card was created")

    def edit(self):
        self.load_card()
        if not self.card:
            raise NotFound

        self.form = CardForm(self.params, self.card)

    def update(self):
        self.load_card()
        if not self.card:
            raise NotFound

        self.form = CardForm(self.params, self.card)
        if self.form.is_invalid:
            return self.redo()

        self.form.save()
        self.response.redirect_to("Card.index", flash="Card was updated")

    def delete(self):
        self.load_card()
        if self.card:
            self.card.delete_instance()
        self.response.redirect_to("Card.index", flash="Card was deleted")

    # Private

    def load_card(self):
        card_id = self.params.get("card_id", "")
        self.card = Card.find(int(card_id)) if card_id.isdigit() else None
```

Key patterns to notice:

- Records and forms are loaded inside each action. There are no `before` callbacks for them: each action shows everything it needs, and nothing depends on the order in which callbacks run.
- `load_card()` is a private helper that sets `self.card` to the record, or to `None` when the ID is missing, not a number, or not in the table. The actions that need an existing record (`show`, `edit`, `update`) raise `NotFound` when it is `None`. `index`, `new`, and `create` don't have an existing record, so they don't call it.
- The form is instantiated with the request params and, for existing records, `self.card` as the second argument (the object). For `new` and `create` there is no object.
- An invalid form ends the action with `return self.redo()`, which re-renders the form template (`new.jx` for `create`, `edit.jx` for `update`) with a `422 Unprocessable Entity` status. The `return` is required: nothing halts automatically inside an action, so without it the code falls through to `form.save()` and the redirect.
- `before` callbacks are for cross-cutting checks that halt the request (authentication, authorization, CSRF, locale). Don't use them to load records or build forms.
- When several actions share form setup that needs extra template context (select options, for example), put it in a private `prepare_form(object=None)` helper that builds the form, sets the extra attributes, and returns the form. The actions call it instead of instantiating the form directly:

```python
def new(self):
    self.form = self.prepare_form()

def edit(self):
    self.load_card()
    if not self.card:
        raise NotFound
    self.form = self.prepare_form(self.card)

# Private

def prepare_form(self, object=None):
    form = CardForm(self.params, object=object)
    self.categories = Category.select().order_by(Category.name)
    return form
```

- After a successful create, update, or delete, the controller redirects with a flash message.
- The `delete` action checks `if self.card` to handle the case where someone deletes the same record twice (e.g., double-clicking the delete button).
- `form.save()` validates the data, persists the model (creating or updating), and returns it. No follow-up `obj.save()` needed. See [Forms — Saving](./forms.md) for details on the integration with Peewee.

### Data Flow: params → action → form → save

This is the complete path data takes through a create or update action.

**Create** (`POST /cards`):

```
self.params  (merged MultiDict: query + form body + route params)
        │
        ▼
create action
  └─ self.form = CardForm(self.params)
  └─ form invalid  → return self.redo() re-renders new.jx with 422
                       (nothing below runs)
  └─ self.form.save()                     # build a new Card from validated data and INSERT
  └─ redirect_to("Card.index")
```

**Update** (`PATCH /cards/:card_id`):

```
self.params
        │
        ▼
update action
  └─ self.load_card()
  └─ raises NotFound if missing
  └─ self.form = CardForm(self.params, self.card)
       Fields pre-filled from self.card; submitted params override
  └─ form invalid  → return self.redo() re-renders edit.jx with 422
                       (nothing below runs)
  └─ self.form.save()                     # mutates self.card and UPDATEs in DB
  └─ redirect_to("Card.index")
```

The key difference: on create, `form.save()` instantiates a **new** model. On update, it mutates the **existing** object passed in as the form's second argument, `self.card`.


Rendering, JSON responses, redirects, flash messages and HTTP errors are in [rendering.md](rendering.md). Callbacks and concerns are in [concerns.md](concerns.md).


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
        self.form = ClientForm(self.params)
        if self.form.is_invalid:
            return self.redo()
        client = self.form.save()
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

### The Request Body

The body is read and parsed before routing, by `Content-Type` (media type and parameter names are case-insensitive):

- `multipart/form-data` → `request.form`: fields as `str`, files as `MultipartPart`
- `application/x-www-form-urlencoded` (or `application/x-url-encoded`) → `request.form`: fields as `str`
- `application/json` → `request.form`: the members of the JSON **object**, with their JSON types. Any other JSON value (array, string, number, `true`, `null`) leaves `form` empty; parse `request.body` yourself.
- anything else → only `request.body`

`request.body` always has the raw bytes. Urlencoded and JSON bodies are decoded with the `charset` parameter (default UTF-8). Errors raised before the controller runs:

| Problem | Error |
|---|---|
| Body over `MAX_CONTENT_LENGTH` (also for chunked/HTTP/2 bodies without `Content-Length`, which are read up to the limit) | `RequestEntityTooLarge` (413) |
| Bytes not valid in the charset | `BadRequest` (400) |
| Unknown charset, or one that can't decode a urlencoded body's percent-escapes (`idna`) | `UnsupportedMediaType` (415) |
| Malformed JSON or multipart (including a missing final boundary), JSON with an integer over 4300 digits, or nested too deep for the stack | `MultipartError` (400) |
| More than `MAX_FORM_FIELDS` (100) fields in a urlencoded or multipart body, more than `MAX_FORM_FILES` (10) files, or a multipart field over `MAX_FORM_PART_SIZE` (2 MB) | `MultipartError` (400) |
| A body shorter or longer than its `Content-Length` | `BadRequest` (400) |

A multipart body is never refused for its charset: with an unknown charset, or for a field not valid in it, the field is read as Latin-1.

### Route Defaults

Routes can define default values that are available in the controller via `self.defaults`:

```python
# In the router:
@router.get("pages/:slug", defaults={"sidebar": True})
def show(self): ...

# In the controller:
self.defaults["sidebar"]   # True
```

A default with the name of a placeholder is what `url_for` fills it with when it isn't given, and can be a function (`lambda: current.account.id`); see [urls.md](urls.md#placeholders-with-defaults).


## Sessions

Session data is a signed cookie, read from `self.request.session` and written to `self.response.session` (a plain `dict`). How it works, flash storage and the cookie settings are in [security.md](security.md#sessions).

```python
user_id = self.request.session.get("user_id")   # set by a previous request
self.response.session["user_id"] = user.id      # sent in the response cookie
```


## HTTP Method Override

A `POST` with `_method=patch|put|delete|query` (a hidden field, a query parameter or the `X-HTTP-Method-Override` header) is rewritten before routing, so `<Form method="patch">` works. Details in [routing.md](routing.md#method-override).
