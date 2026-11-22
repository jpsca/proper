---
title: Building API-only Applications
description: |
  A Proper application can answer with JSON instead of HTML, for a mobile app, a JavaScript front end, or other programs. This guide shows how to write JSON controllers, read and validate JSON input, return errors as JSON, authenticate with tokens, and paginate, rate limit, version and test an API.
number_headers: true
---

# Building API-only Applications

In this guide, you will learn how to build an application that talks to other programs instead of to people in a browser.

- What changes, and what stays the same, when your application returns JSON.
- How to write a base controller for your API.
- How to turn records into JSON and read the JSON a client sends.
- How to validate input with the same forms you use for HTML.
- How to return every error as JSON.
- How to authenticate clients with tokens instead of cookies.
- How to paginate, rate limit, and version an API.
- How to let a JavaScript application on another domain call it.
- How to test all of it.

---

## Introduction

An API is a set of URLs that programs call instead of people. A mobile app asks for the list of cards, or a JavaScript front end creates one. The client sends JSON and gets JSON back.

If you come from Flask, FastAPI, or Django REST Framework, you may be looking for an "API mode" or a package to install. Proper has neither. An API is made of ordinary controllers, and the router, the models, the forms, the tasks, and the test client work as they do in any other application. A few things change:

Instead of...                     | An API uses...
--------------------------------- | ------------------------------------------
Rendering a Jx component          | `self.render(json=...)`
Re-rendering the form on an error | A `422` response with the errors as JSON
A sign-in page and a cookie       | A token in the `Authorization` header
HTML error pages                  | JSON error responses
Redirecting after a `POST`        | A `201` response with the new record

This guide builds a small API for a `Card` model with a `title`, a `body`, and a `priority`. It assumes you have read [Getting Started](/docs/getting_started) and the [Controllers Overview](/docs/controllers).

:::note | One or two endpoints in an HTML application?
If your application is mostly HTML and only a couple of actions also need to answer JSON, you don't need this guide. Read [Serving JSON Alongside HTML](/docs/controllers_advanced#serving-json-alongside-html) instead.
:::

### Do I Need a Separate Application?

No. The API can be the whole application, or it can live next to your HTML pages. This guide puts everything under `/api/v1` and in its own folder, which works for both cases:

```
myapp/controllers/
├── __init__.py
├── app_controller.py
├── public_controller.py
└── api/
    ├── __init__.py
    ├── api_controller.py
    ├── card_controller.py
    └── error_controller.py
```

A new application comes with views, assets, and a session cookie. An API doesn't use them, and you can leave them where they are. The health page at `/up` is still useful for your deployment.

---

## A First Endpoint

### The Scoped Router

Start by giving the API its own URL prefix. A [scope](/docs/routing#scopes) is a router that adds a prefix to every route registered through it:

```python {title="myapp/router.py"}
api_router = router.scope("api/v1")
```

### The Base Controller

Next, write a base controller for the API. Every API controller will inherit from it, the same way your HTML controllers inherit from `AppController`:

```python {title="myapp/controllers/api/api_controller.py"}
from proper import Controller
from proper.concerns import OriginProtection, Pagination, RateLimiting


class ApiController(
    OriginProtection,
    Pagination,
    RateLimiting,
    Controller,
):
    """All the API controllers must inherit from this class."""

    before = {"do": "disable_cookies"}

    def disable_cookies(self):
        self.response.disable_cookies = True
```

It doesn't inherit from `AppController` on purpose. `AppController` is set up for browsers: it adds security headers for HTML pages and, if you installed the authentication addon, it sends visitors without a session to the sign-in page. A program that calls your API needs neither.

`disable_cookies` tells the response to never send a `Set-Cookie` header. API clients identify themselves with a token on each request, so they have nothing to do with a cookie.

### The Controller

The controller for the cards inherits from it:

```python {title="myapp/controllers/api/card_controller.py"}
from myapp.models import Card
from myapp.router import api_router
from .api_controller import ApiController


@api_router.resource("cards")
class CardController(ApiController):
    def index(self):
        cards = Card.select().order_by(Card.id)
        return self.render(json=[
            {"id": card.id, "title": card.title} for card in cards
        ])
```

`self.render(json=...)` turns the value into JSON and sets the `Content-Type` header to `application/json`. It returns the text, and what an action returns is the body of the response.

Routes are registered when the controller is imported, so import the new file:

```python {title="myapp/controllers/api/__init__.py"}
from . import card_controller  # noqa
```

```python {title="myapp/controllers/__init__.py"}
from . import public_controller  # noqa
from . import api  # noqa
```

Start the server with `proper run` and call the endpoint:

```bash
$ curl http://localhost:2300/api/v1/cards
[{"id": 1, "title": "Buy milk"}, {"id": 2, "title": "Call Ana"}]
```

Run `proper routes` to see the routes you have. A controller inside `controllers/api/` gets the `Api:` prefix in its route names, so this one is `Api:Card.index`.

:::tip | Only the actions you write get a route
`@api_router.resource` adds a route for each of the standard actions it finds in the class: `index`, `show`, `create`, `update`, and `delete`. An API has no forms to show, so you never write `new` or `edit`, and those routes don't exist.
:::

---

## Turning Records into JSON

### A Function per Record

Proper doesn't have serializer classes. A record becomes JSON through a plain dictionary, and the simplest place to build that dictionary is a function:

```python {title="myapp/controllers/api/card_controller.py"}
def card_json(card):
    return {
        "id": card.id,
        "title": card.title,
        "body": card.body,
        "priority": card.priority,
        "created_at": card.created_at,
    }
```

Use it everywhere a card goes out:

```python
def index(self):
    cards = Card.select().order_by(Card.id)
    return self.render(json=[card_json(card) for card in cards])

def show(self):
    card = self.load_card()
    return self.render(json=card_json(card))
```

Listing the fields by hand takes a few more lines than sending the whole record. In exchange, your clients only see what you chose to send. A column you add to the table next month, like `internal_notes`, doesn't go out by accident, and you can rename a column without breaking every client.

When several controllers need the same function, move it to its own module, for example `myapp/serializers.py`. If you prefer, a `to_json()` method on the model works too.

### Dates and Times

JSON has no type for dates. `self.render(json=...)` writes `date` and `datetime` values as text in the ISO 8601 format, which every language can read:

```json
{"id": 1, "title": "Buy milk", "created_at": "2026-11-22T10:30:00"}
```

The `created_at` of a model is in UTC and has no timezone information, so the text has none either. Tell your clients the times are UTC, or write the value yourself with a `Z` at the end: `card.created_at.isoformat() + "Z"`.

Any other value that JSON doesn't know, like a `Decimal` or a `set`, raises a `TypeError`. Turn it into a number, a string, or a list in the dictionary.

### Loading One Record

The `show` action above calls `load_card`. It reads the ID from the URL and raises `NotFound` when there is no such card:

```python
from proper.errors import NotFound

# ... inside CardController ...

def load_card(self):
    card_id = str(self.params.get("card_id", ""))
    card = Card.find(int(card_id)) if card_id.isdigit() else None
    if card is None:
        raise NotFound("Card not found")
    return card
```

Raising the error stops the action. [Errors as JSON](#errors-as-json) shows how that becomes a JSON response.

---

## Reading JSON Input

When a client sends a body with `Content-Type: application/json`, Proper reads it before your action runs. If the body is a JSON object, its members are in `self.params`, next to the values from the URL and the query string:

```bash
$ curl -X POST http://localhost:2300/api/v1/cards \
    -H "Content-Type: application/json" \
    -d '{"title": "Buy milk", "priority": 2}'
```

```python
def create(self):
    self.params["title"]     # "Buy milk"
    self.params["priority"]  # 2
```

Unlike the values of an HTML form, which are always text, these keep their JSON types: `2` is an `int`, `true` is `True`, and a list is a `list`.

A body that is not an object, like a JSON array, isn't put in `self.params`. Read it from `self.request.body`, which always has the raw bytes:

```python
import json

def create_many(self):
    items = json.loads(self.request.body)  # [{"title": "..."}, {"title": "..."}]
```

Proper refuses a body that isn't valid JSON with a `400 Bad Request` before the request reaches your controller, and one that is too big with a `413`. The [Controllers Overview](/docs/controllers#the-request-body) has the full list.

:::note | The header matters
Without `Content-Type: application/json`, Proper doesn't treat the body as JSON and `self.params` won't have its values. It is the first thing to check when a client says "I'm sending the data but the server doesn't see it".
:::

---

## Validating Input

Never save `self.params` directly. A client can send any field, with any value. In Proper, [forms](/docs/forms) decide which fields are accepted and check their values, and they do it for JSON as well as for HTML.

Here is the form for a card:

```python {title="myapp/forms/card.py"}
from proper import forms as f

from ..models import Card


class CardForm(f.Form):
    class Meta:
        orm_cls = Card

    title = f.TextField()
    body = f.TextField(required=False)
    priority = f.IntegerField(required=False, default=0)
```

And the actions that use it:

```python {title="myapp/controllers/api/card_controller.py"}
from proper import status

from myapp.forms.card import CardForm

# ... inside CardController ...

def create(self):
    form = CardForm(self.params)
    if form.is_invalid:
        return self.render(
            json={"errors": form.get_errors()},
            status=status.unprocessable,
        )
    card = form.save()
    return self.render(json=card_json(card), status=status.created)

def update(self):
    form = CardForm(self.params, self.load_card())
    if form.is_invalid:
        return self.render(
            json={"errors": form.get_errors()},
            status=status.unprocessable,
        )
    card = form.save()
    return self.render(json=card_json(card))

def delete(self):
    self.load_card().delete_instance()
    self.response.status = status.no_content
    return ""
```

The flow is the one of an HTML controller, with two differences.

The first is what happens with an invalid form. In an HTML controller it ends with `return self.redo()`, which shows the form again. An API has no form to show, so it sends the errors. `form.get_errors()` returns a dictionary with the name of each field that failed and the code of its error:

```bash
$ curl -X POST http://localhost:2300/api/v1/cards \
    -H "Content-Type: application/json" \
    -d '{"body": "No title"}'
{"errors": {"title": "required"}}
```

The codes (`required`, `invalid`, `max_length`, ...) are short and stable, so a client can show its own message for each one, in its own language.

The other difference is the end of the action. An HTML controller redirects after saving. An API answers with the record and the status that describes what happened:

Action   | Status              | Body
-------- | ------------------- | ---------------------
`index`  | `200 OK`            | The list of records
`show`   | `200 OK`            | The record
`create` | `201 Created`       | The new record
`update` | `200 OK`            | The updated record
`delete` | `204 No Content`    | Empty

The codes are in `proper.status`, so you can write `status.created` instead of remembering `201`.

Fields the form doesn't declare are ignored. If a client sends `{"title": "Hi", "is_admin": true}`, only `title` is used.

:::tip | `PATCH` and `PUT`
Both are routed to `update`. Because the form receives the existing card as its second argument, a client can send only the fields it wants to change, and the rest keep their values.
:::

---

## Errors as JSON

Things go wrong in ways your actions don't handle one by one: a URL that doesn't exist, a card that was deleted, a bug. Proper answers those with an HTML page, and a program that expects JSON can't read it.

### An Error Controller

Register a handler for a class of errors with `@router.error`. Two handlers are enough:

```python {title="myapp/controllers/api/error_controller.py"}
from proper import Controller, errors

from myapp.router import router


class ErrorController(Controller):
    @router.error(errors.HTTPError)
    def http_error(self):
        error = self.response.error
        message = str(error) or type(error).__name__
        return self.render(json={"error": message})

    @router.error(Exception)
    def server_error(self):
        return self.render(json={"error": "Internal server error"})
```

Import it in `controllers/api/__init__.py`, like the other controllers.

`HTTPError` is the parent of every error that has a status: `NotFound`, `Forbidden`, `Unauthorized`, `MethodNotAllowed`, and the others in [the list of error classes](/docs/controllers_advanced#the-error-classes). When one is raised, the response already has the right status by the time the handler runs, so the handler only writes the body. The error itself is in `self.response.error`.

The second handler catches everything else, which means bugs. It answers with a fixed message and a `500` status. Don't put the text of the error there: it could show a client a piece of your code or your data. The full error goes to your logs.

With these two, the `NotFound` raised by `load_card` becomes:

```bash
$ curl -i http://localhost:2300/api/v1/cards/999
HTTP/1.1 404 Not Found
Content-Type: application/json; charset=utf-8

{"error": "Card not found"}
```

:::note | Handlers are for the whole application
`@router.error` is not limited to the URLs of the API. If your application also has HTML pages, check `self.request.path.startswith("/api/")` in the handler, and render your HTML error page otherwise.
:::

### Raise or Return?

The controller answers with errors in two ways. `create` *returns* a `422` with the form errors, and `load_card` *raises* `NotFound`.

Return when the action wants to say something specific in the body, like the errors of each field. Raise for everything else: it works from any method, not only from the action, and the error controller gives all those responses the same shape.

You can raise any error with your own message:

```python
from proper.errors import Conflict, Forbidden

if card.is_archived:
    raise Conflict("An archived card can't be changed")

if card.owner_id != current.user.id:
    raise Forbidden("This card belongs to someone else")
```

### Errors While Developing

Your handlers only run when `DEBUG` is off. While you develop, Proper answers every error with its debug information instead, so you can find the bug. A client that asks for JSON gets it as JSON:

```bash
$ curl -H "Accept: application/json" http://localhost:2300/api/v1/cards/999
{"error": "NotFound", "message": "Card not found", "details": "..."}
```

`details` has the traceback and the request. Without the `Accept` header, the same information comes as plain text, which is easier to read in a terminal.

To see your own error responses, write a test for them (the test application runs with `DEBUG` off) or start the server with `DEBUG` off.

---

## Authentication with Tokens

A browser proves who the user is with a cookie. A program does it with a *token*: a long random text it sends in a header with every request.

```
Authorization: Bearer 3q2-7wEJ0bLk...
```

Proper's [authentication addon](/docs/authentication) is made for browsers, with sign-in pages and cookies. For an API you write the token part yourself, with a model and a concern.

### The Token Model

```python {title="myapp/models/api_token.py"}
import hashlib
import secrets

import peewee as pw

from .base import BaseModel
from .user import User


class ApiToken(BaseModel):
    user = pw.ForeignKeyField(User, backref="api_tokens", on_delete="CASCADE")
    name = pw.CharField(default="")
    digest = pw.CharField(max_length=64, unique=True)

    @classmethod
    def issue(cls, user, name=""):
        """Creates a token for the user and returns its text.
        This is the only time the text can be read."""
        token = secrets.token_urlsafe(32)
        cls.create(user=user, name=name, digest=cls.digest_of(token))
        return token

    @classmethod
    def find_user(cls, token):
        row = cls.get_or_none(cls.digest == cls.digest_of(token))
        return row.user if row else None

    @staticmethod
    def digest_of(token):
        return hashlib.sha256(token.encode()).hexdigest()
```

Add it to `models/__init__.py`, then run `proper db create api_token` and `proper db migrate` to make the table.

The table stores a SHA-256 digest of each token, never the token. If someone reads your database, they can't use what they find to call your API. The cost is that you can show a token only once, when you create it. That is why services that give you an API key tell you to copy it right away.

To give a user a token, call `issue` wherever makes sense in your application: a settings page, a command, or the console.

```python
>>> ApiToken.issue(user, name="Mobile app")
'3q2-7wEJ0bLkYz1mN8aXfR5tUv0cHdGpWsQeIoA9B4M'
```

To revoke a token, delete its row.

### The Concern

```python {title="myapp/controllers/concerns/token_authentication.py"}
from proper import Concern, current
from proper.errors import Unauthorized

from myapp.models import ApiToken


class TokenAuthentication(Concern):
    before = {"do": "require_token"}

    # `True` to make the whole controller public,
    # or a list with the names of the public actions.
    skip_authentication = ()

    def require_token(self):
        skip = self.skip_authentication
        if skip is True or self.request.matched_action in skip:
            return

        header = self.request.headers.get("authorization") or ""
        scheme, _, token = header.partition(" ")
        user = ApiToken.find_user(token) if scheme.lower() == "bearer" else None
        if user is None:
            raise Unauthorized(
                "Missing or invalid token",
                **{"WWW-Authenticate": "Bearer"},
            )
        current.user = user
```

The callback reads the header, looks for the user of that token, and stores it in `current.user`, where your actions and models can read it. Without a valid token it raises `Unauthorized`, and the error controller turns that into a `401` response. The extra argument adds a `WWW-Authenticate` header to it, which tells the client what kind of credentials you expect.

Add the concern to `ApiController`, at the end of the list of concerns:

```python {title="myapp/controllers/api/api_controller.py"}
from ..concerns.token_authentication import TokenAuthentication


class ApiController(
    OriginProtection,
    Pagination,
    RateLimiting,
    TokenAuthentication,
    Controller,
):
    ...
```

:::note | Why at the end?
The `before` callbacks of the classes in that list run from the last one to the first. With `TokenAuthentication` last, it runs first, so `current.user` is already set when the other callbacks run. [Rate Limiting](#rate-limiting) below depends on it.
:::

Every endpoint now needs a token:

```bash
$ curl -i http://localhost:2300/api/v1/cards
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer

{"error": "Missing or invalid token"}

$ curl -H "Authorization: Bearer 3q2-7wEJ0bLk..." http://localhost:2300/api/v1/cards
[{"id": 1, "title": "Buy milk", ...}]
```

To leave some actions open, list them:

```python
class CardController(ApiController):
    skip_authentication = ["index", "show"]
```

### Only the User's Records

The token says who the user is. What that user can see is up to your code. Start every query from the user, and a card that belongs to someone else is not found. The examples below assume `Card` has a `user` foreign key with `backref="cards"`:

```python
def index(self):
    cards = current.user.cards.order_by(Card.id)
    return self.render(json=[card_json(card) for card in cards])

def load_card(self):
    card_id = str(self.params.get("card_id", ""))
    card = None
    if card_id.isdigit():
        card = current.user.cards.where(Card.id == int(card_id)).first()
    if card is None:
        raise NotFound("Card not found")
    return card
```

And when creating one, the owner comes from the token, never from the request:

```python
card = form.save(user_id=current.user.id)
```

The [Authentication guide](/docs/authentication) and the [Security guide](/docs/security#authorization) say more about authorization.

:::warning | Tokens need HTTPS
A token travels with every request. Over plain HTTP anyone on the way can read it and use it. Serve your API over HTTPS only. See the [Deployment guide](/docs/deployment).
:::

---

## Pagination

An endpoint that returns every row gets slower as the table grows. `ApiController` includes the `Pagination` concern, so `index` can return one page at a time:

```python
def index(self):
    cards = self.paginate_for(
        current.user.cards.order_by(Card.id),
        per_page=50,
    )
    return self.render(json=[card_json(card) for card in cards])
```

`paginate_for` reads the `page` parameter of the request and returns the records of that page. On a JSON response it also adds two headers, so the body stays a plain list:

```bash
$ curl -i -H "Authorization: Bearer ..." "http://localhost:2300/api/v1/cards?page=2"
HTTP/1.1 200 OK
X-Total-Count: 132
Link: </api/v1/cards?page=3>; rel="next"
```

`X-Total-Count` is the number of records in all the pages. `Link` has the URL of the next page, and it is missing on the last one. A client keeps following it until it is gone.

For a table with a lot of rows, or one that changes while clients read it, pass `ordered_by` to page with a cursor instead of a page number. The [Controllers Overview](/docs/controllers#pagination) explains both modes.

---

## Rate Limiting

A program with a bug in a loop can call your API thousands of times a minute. The `RateLimiting` concern, also in `ApiController`, sets a limit:

```python {title="myapp/controllers/api/api_controller.py"}
from proper import current
from proper.units import MINUTE


class ApiController(...):
    rate_limit = {
        "to": 120,
        "within": 1 * MINUTE,
        "by": "rate_limit_identity",
        "scope": "api",
    }

    def rate_limit_identity(self):
        if current.user:
            return f"user-{current.user.id}"
        return self.request.remote_ip
```

This allows each user 120 requests per minute. A request over the limit raises `TooManyRequests`, and the error controller answers with a `429`.

- `by` names the method that says who is calling. Without it the limit is by IP address, which is unfair to users behind the same office network and easy to dodge for someone with many addresses. By user is the better default for an API with tokens. The method falls back to the IP address for the public actions, which have no user.
- `scope` makes all the API controllers share one counter. Without it, each controller counts on its own.

A controller can set its own `rate_limit` to replace this one, for example a stricter limit on an expensive search.

:::warning | Rate limits need a cache
The counters are kept in the cache. If your application has no cache configured, the limits are ignored without any error. See the [Caching guide](/docs/caching) and the [rate limiting section](/docs/security#rate-limiting) of the Security guide.
:::

---

## Calling the API from a Browser

Skip this section if your clients are mobile apps or other servers. It only matters when JavaScript running on *another* site, like a front end at `https://app.example.com`, calls your API at `https://api.example.com`.

Two things stop those requests, and both exist to protect your users.

### Origin Protection

`OriginProtection` refuses any request from a browser that changes something (`POST`, `PATCH`, `PUT`, `DELETE`) and comes from a different site. It answers with a `403`. Requests from programs that are not browsers don't have the headers it looks at, and pass through.

Tell it which sites you trust:

```python {title="myapp/config/main.py"}
TRUSTED_ORIGINS = [
    "https://app.example.com",
]
```

Each entry is the scheme, the host, and the port if it isn't the default one, with no slash at the end.

### CORS

The browser itself also refuses to show a response to a page of another site, unless the response has headers that allow it. This is called CORS. Proper doesn't add those headers for you, but a small concern can:

```python {title="myapp/controllers/concerns/cors.py"}
from proper import Concern


class Cors(Concern):
    after = {"do": "set_cors_headers"}

    def set_cors_headers(self):
        origin = self.request.headers.get("origin")
        if origin not in self.app.config.get("TRUSTED_ORIGINS", []):
            return
        headers = self.response.headers
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE"
        headers["Access-Control-Expose-Headers"] = "Link, X-Total-Count"
        self.response.set_vary("Origin")
```

It uses the same list of trusted sites, so there is one place to edit. Add `Cors` to the list of concerns of `ApiController`, and also to `ErrorController`:

```python
class ErrorController(Cors, Controller):
    ...
```

The second one is easy to forget. `after` callbacks don't run when an action raises an error, so without it your `401` and `404` responses would have no CORS headers, and the browser would report a CORS failure instead of the real error.

### Preflight Requests

Before a request with a JSON body or an `Authorization` header, the browser first sends an `OPTIONS` request to the same URL, to ask for permission. It needs a route too. One route can answer for the whole API:

```python {title="myapp/controllers/api/preflight_controller.py"}
from proper import status

from myapp.router import api_router
from .api_controller import ApiController


class PreflightController(ApiController):
    skip_authentication = True

    @api_router.options(":path<path>")
    def preflight(self):
        self.response.status = status.no_content
        return ""
```

The browser doesn't send the token with this request, which is why the controller skips the authentication. The `Cors` concern adds the headers, as it does for every other action.

:::note | A side effect
With this route, a `GET` to a URL of the API that doesn't exist is answered with `405 Method Not Allowed` instead of `404 Not Found`, because the URL does match a route, only not for that method.
:::

---

## Versioning

You can't update the programs that call your API. A mobile app installed two years ago still calls the URLs it was built with. So when you have to change the shape of a response in a way that would break them, you publish the change as a new version and keep the old one working.

That is the reason the routes of this guide start with `/api/v1`. A second version is a second scope:

```python {title="myapp/router.py"}
api_router = router.scope("api/v1")
api_v2_router = router.scope("api/v2")
```

The controllers of the new version go in their own folder, `controllers/api_v2/`, and use `api_v2_router`. They can inherit from the old ones and change only what is different:

```python {title="myapp/controllers/api_v2/card_controller.py"}
from myapp.router import api_v2_router
from ..api.card_controller import CardController as V1CardController


@api_v2_router.resource("cards")
class CardController(V1CardController):
    def index(self):
        ...
```

You don't need a new version to *add* something. A new endpoint or a new field in a response doesn't break a client that ignores it. Save new versions for removing or renaming.

If you want the API on its own subdomain, a scope takes a `host` too:

```python
api_router = router.scope("v1", host="api.example.com")
```

See [Host-Based Routing](/docs/routing#host-based-routing) in the Routing guide.

---

## Testing

API tests use the same [test client](/docs/testing) as any other test. A fixture that sends JSON with the token saves repeating both in every test:

```python {title="tests/conftest.py"}
import json

import pytest

from myapp.models import ApiToken, User


@pytest.fixture()
def user():
    return User.create(login="ana@example.com", name="Ana")


@pytest.fixture()
def api(client, user):
    token = ApiToken.issue(user)
    headers = {
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
    }

    def call(method, url, data=None):
        send = getattr(client, method)
        if data is None:
            return send(url, headers=headers)
        return send(url, body=json.dumps(data), headers=headers)

    return call
```

Change the `user` fixture to match the fields of your own `User` model.

```python {title="tests/controllers/api/test_card.py"}
import json

from myapp.main import app
from myapp.models import Card


def test_index_needs_a_token(client):
    result = client.get(app.url_for("Api:Card.index"))

    assert result.status == 401
    assert result.headers["www-authenticate"] == "Bearer"


def test_create(api, user):
    result = api("post", app.url_for("Api:Card.create"), {"title": "Buy milk"})

    assert result.status == 201
    assert result.mimetype == "application/json"
    data = json.loads(result.body)
    assert data["title"] == "Buy milk"
    assert Card.get_by_id(data["id"]).user_id == user.id


def test_create_without_a_title(api):
    result = api("post", app.url_for("Api:Card.create"), {"body": "No title"})

    assert result.status == 422
    assert json.loads(result.body) == {"errors": {"title": "required"}}


def test_show_a_card_of_someone_else(api):
    other = User.create(login="luis@example.com", name="Luis")
    card = Card.create(title="Private", user=other)

    result = api("get", app.url_for("Api:Card.show", card))

    assert result.status == 404
    assert json.loads(result.body) == {"error": "Card not found"}
```

`result.body` is the text of the response, so `json.loads` turns it back into Python values. `app.url_for` builds the URL from the name of the route, and the tests keep working if you move the API to another prefix.

Write a test like the last one for every endpoint: one user asking for the record of another. You won't notice that mistake when you try the API by hand with your own account.

---

## What's Next

- [Controllers Advanced Topics](/docs/controllers_advanced) covers `fresh_when`, which lets a client that already has the current version of a record get an empty `304` response instead of the whole body. It works for JSON as it does for HTML.
- [Routing](/docs/routing) has everything about scopes, hosts, and placeholders.
- [Working with Forms](/docs/forms) explains the fields, the validators, and how `save()` works.
- [Background Tasks](/docs/tasks) is where slow work belongs. An endpoint that starts a long job should queue it and answer with `202 Accepted` right away.
- [Security](/docs/security) has a checklist to go through before your API is public.
- [Testing Proper Applications](/docs/testing) describes the test client in full.
