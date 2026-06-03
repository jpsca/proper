---
title: Controllers Advanced Topics
description: |
  The Controllers Overview covered the day-to-day shape of a controller. This guide picks up where it stops - the topics that don't come up on every page, but that you will reach for sooner or later: HTTP errors, conditional GETs, file downloads, controllers that don't fit the CRUD mold, and the harder corners of rate limiting.
number_headers: true
---

# Controllers Advanced Topics

This guide collects the controller features the [Controllers Overview](/docs/controllers) deliberately left for later. Each section is independent - read whichever applies to the problem in front of you.

---

## When CRUD Doesn't Fit: A New Controller

Sooner or later you'll have a resource that needs an action that isn't one of the seven CRUD verbs. A card that can be closed and reopened. A user account that can be invited, suspended, restored. A subscription that can be cancelled, paused, resumed.

The temptation is to add the action as a method on the existing controller and route it manually. Don't.

### The Tempting (Bad) Version

```python {title="myapp/controllers/card_controller.py"}
@router.resource("cards")
class CardController(AppController):

    @router.patch("cards/:card_id/close")
    def close(self):
        ...

    @router.patch("cards/:card_id/reopen")
    def reopen(self):
        ...

    @router.patch("cards/:card_id/not-now")
    def not_now(self):
        ...

    # ... and the seven CRUD actions are still in here ...
```

Three problems with this. The controller bloats with every new state transition. The route names don't follow any convention (`Card.close` vs `Card.create`). And every new action invents its own URL shape, leaving you to remember whether it was `/close`, `/closed`, or `/closure`.

### The Pattern: a Controller per State Change

Each state change is its own resource - it has a way to make it happen (`create`) and, often, a way to undo it (`delete`). Mount it under the parent's URL with `pk=None`:

```python {title="myapp/controllers/card/closure_controller.py"}
from ...router import router
from ..concerns.card_scoped import CardScoped
from ..app_controller import AppController


@router.resource("cards/:card_id/closure", pk=None)
class ClosureController(CardScoped, AppController):

    # POST /cards/:card_id/closure
    def create(self):
        self.card.close()
        self.response.redirect_to("Card.show", self.card, flash="Card closed")

    # DELETE /cards/:card_id/closure
    def delete(self):
        self.card.reopen()
        self.response.redirect_to("Card.show", self.card, flash="Card reopened")
```

```python {title="myapp/controllers/card/not_now_controller.py"}
@router.resource("cards/:card_id/not-now", pk=None)
class NotNowController(CardScoped, AppController):

    def create(self):
        self.card.postpone()
        self.response.redirect_to("Card.show", self.card)
```

`pk=None` drops the trailing ID from the URL: there's only ever one closure for a card, so `/cards/42/closure` is the whole address.

### The `CardScoped` Concern

Every controller in this family loads the parent card from `:card_id`. That's a single piece of behavior shared across many controllers, which is exactly what concerns are for:

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

Mix it in ahead of `AppController` so its `before` callback runs after `AppController`'s but before the action:

```python
class ClosureController(CardScoped, AppController):
    ...
```

### Folder Layout

Once the card has more than one controller, group them under a subfolder:

```
myapp/controllers/
├── app_controller.py
├── card_controller.py             # the original
├── card/
│   ├── __init__.py
│   ├── closure_controller.py
│   └── not_now_controller.py
└── concerns/
    └── card_scoped.py
```

The original `card_controller.py` can stay where it is, or move to `card/main_controller.py` if you'd rather have everything in one folder. Either way, update `controllers/__init__.py` to import the new files - the generator does this for you when you run `proper g controller card/closure --namespace=...` or similar.

### Why This Works Better

- Each controller is small and stays small. Adding a new state change adds a file, not a method.
- Route names follow the standard `Controller.action` convention: `Closure.create`, `Closure.delete`, `NotNow.create`. The same template machinery, the same URL helpers, the same callbacks.
- The state change has a URL shape you can describe in one sentence: "POST creates the closure, DELETE removes it." That maps cleanly onto the buttons in your UI - one form per controller, one submit per state change.
- `CardScoped` is reused across every child controller, including any future ones, so loading the parent card is wired up automatically.

The only thing you give up is the sentimental satisfaction of a "fat controller." That's a feature.

---

## Sending Files

Some actions return a file from disk - a generated PDF, an exported CSV, a stored upload. Use `self.response.send_file`:

```python
def download(self):
    self.response.send_file("/var/exports/q4-report.pdf")
```

That sets the content type from the file extension, sets `Content-Length`, sets `Last-Modified` from the file's mtime, and streams the file to the client. You don't need to return anything from the action; `send_file` populates the response body itself.

### Inline vs. Attachment

By default, the file is served inline - the browser displays it if it can (PDFs, images, plain text), or downloads it if it can't. To force the download dialog, pass `as_attachment=True`:

```python
def download(self):
    self.response.send_file(
        "/var/exports/q4-report.pdf",
        as_attachment=True,
        download_name="Q4-Report.pdf",
    )
```

`download_name` is what the browser will save the file as. If you don't pass it, the actual filename on disk is used. Set it whenever the on-disk name is ugly or contains a hash you'd rather not show the user.

### Mimetype

`send_file` guesses the content type from the path's extension. If the guess is wrong, or the file has no extension, override it:

```python
self.response.send_file(path, mimetype="application/x-custom-format")
```

### Delegating to a proxy (`x_sendfile_header`)

In production, sending megabytes of file through Python is a waste of a worker process. Most reverse proxies support a "send this file for me" header: NGINX and Caddy call it `X-Accel-Redirect`, Apache calls it `X-Sendfile`, etc.

Pass the header name to `send_file` and Proper will set it instead of streaming the file itself:

```python
self.response.send_file(
    filepath,
    as_attachment=True,
    download_name="Q4-Report.pdf",
    x_sendfile_header="X-Accel-Redirect", # NGINX
)
```

The response body becomes empty; the proxy reads the header, opens the file itself, and streams it to the client. Your worker is freed up immediately.

This only works when the proxy is configured to honor the header *and* has read access to the file's directory. In development, leave `x_sendfile_header` unset and let Python serve the file.

:::note | Storing user uploads
For files attached to a model record - profile pictures, document uploads, image variants - reach for the [File Storage](/docs/storage) addon instead of writing `send_file` calls by hand. It gives you S3 support, signed URLs, content-type validation, and image variants without you wiring any of that up. `send_file` is the right primitive when you have a file path on disk and want to serve it; Storage is the right addon when you have an *attachment* tied to a record.
:::

---

## Rate Limiting the Hard Cases

The [Controllers Overview](/docs/controllers#concerns) covers the common case for `rate_limit`: a fixed number of requests per IP, applied to one or two actions. This section covers what that summary skipped.

```python
from proper.units import MINUTES

class SessionController(AppController):
    rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}
```

That's the baseline: ten POSTs to `Session.create` per IP per three minutes. Beyond that limit, the framework raises `429 Too Many Requests`. The full options table is below; everything else in this section is "what the defaults aren't doing for you."

| Option       | Description                                          | Default                       |
| ------------ | ---------------------------------------------------- | ----------------------------- |
| `to`         | Max requests allowed (int, method name, or callable) | (required)                    |
| `within`     | Time window in seconds                               | (required)                    |
| `only`       | Action(s) to apply the limit to                      | all actions                   |
| `exclude`    | Action(s) to exclude from the limit                  | none                          |
| `by`         | Identity function (method name or callable)          | IP address                    |
| `scope`      | Scope string for grouping limits                     | controller module path        |
| `name`       | Name to distinguish multiple limits in same scope    | `""`                          |
| `react_with` | Method or callable to handle exceeding the limit     | raise `TooManyRequests`        |

### `by`: Limit by Something Other Than IP

The default identity is the client's IP address. That's often the wrong thing - especially for login forms, where attackers cycle through IPs but always submit the same email. Pass a `by` callable to use a different identity:

```python
class SessionController(AppController):
    rate_limit = {
        "to": 8,
        "within": 15 * MINUTES,
        "only": "create",
        "by": lambda self: self.login_param,
    }

    @property
    def login_param(self):
        return User.normalize_login(self.params.get("login") or "")
```

Now eight failed login attempts for the *same email* within fifteen minutes triggers the limit, regardless of which IP they came from. An attacker can rotate IPs all day and still get throttled.

`by` accepts either a callable (typically a `lambda self:`) or a string method name. The latter reads better when the identity logic is non-trivial.

### `react_with`: Don't Raise, Do Something Else

The default reaction to a hit is `raise TooManyRequests`. That returns a 429 with whatever your `Exception` error handler renders. For a public API that's right; for a login form, you usually want to redirect back with a flash message instead:

```python
class SessionController(AppController):
    rate_limit = {
        "to": 8,
        "within": 15 * MINUTES,
        "only": "create",
        "by": lambda self: self.login_param,
        "react_with": "too_many_retries",
    }

    def too_many_retries(self):
        self.response.redirect_to(
            "Session.new",
            flash="Try again in a few minutes or reset your password.",
            flash_cat="negative",
        )
```

`react_with` can be either a method name (resolved on the controller) or a callable. The method runs in place of the action; whatever it sets on `self.response` becomes the response.

### Multiple Limits at Once

A class attribute can hold a list of limit dicts. Each one is checked independently:

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
```

The first limit catches an attacker brute-forcing one account; the second catches a single IP that's brute-forcing many accounts. Both apply to `create`. If both would trigger, both react in order - in practice, the first one's `react_with` short-circuits the dispatch, so the second one doesn't get a chance to raise.

### Dynamic Limits

`to` and `within` accept method names instead of literals. Use this when the limit depends on something the controller can compute - the user's plan, the time of day, a feature flag:

```python
from proper.units import MINUTE, HOUR

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

The methods are called per-request, so the answer can change at any time without restarting the app.

### Resetting a Limit

After a successful login, you don't want a user's previous failed attempts counting against them. Call `reset_rate_limit` with the same identity the limit was keyed on:

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
    ]

    def create(self):
        user = User.authenticate(self.params)
        if not user:
            return self.redo()

        self.reset_rate_limit(self.login_param)   # clear failed attempts
        login(user)
        self.response.redirect_to("Home.show")
```

The argument is the identity value, not the callable that produced it. If you have several limits with different `by`s, call `reset_rate_limit` once per identity you want to clear.

:::note | Rate limiting needs a cache store
The framework uses the cache as the counter store. If no cache is configured, `rate_limit` is silently ignored - no error, no warning, no protection. The default development config uses an in-memory SQLite cache, which works for development but resets on every restart. The [Caching guide](/docs/caching) covers production configurations.
:::

The [Security guide](/docs/security) has more on rate limiting from the threat-model side - what to limit, what to leave alone, and how it interacts with login forms, password resets, and API tokens.

---

## Serving JSON Alongside HTML

Most controllers in a Proper app return HTML. But occasionally a single URL needs to serve both - the same `Card.show` action might render a page for a browser and return a JSON document for a JavaScript client that calls the same URL with `Accept: application/json`. This section covers how to write that controller and the one cache-related pitfall that comes with it.

### `self.request.format`

`self.request.format` parses the request's `Accept` header and tells you what the client asked for: `"html"`, `"json"`, `"xml"`, and so on. Branch on it:

```python
def show(self):
    self.card = Card.get_or_none(self.params["card_id"])
    if not self.card:
        raise NotFound

    if self.request.format == "json":
        return self.render(json={"id": self.card.id, "title": self.card.title})

    # falls through; renders card/show.jx implicitly
```

When the `Accept` header is missing or matches `*/*`, `format` falls back to `request.default_format`, which is `"html"` unless you've changed it. So a curl with no `-H 'Accept: ...'` lands in the HTML branch, which is usually what you want.

You can also lean on the implicit-rendering machinery, which already understands format-specific templates: a request for JSON will pick `card/show.json.jx` ahead of `card/show.jx` if both exist. That's worth knowing when the JSON shape is non-trivial enough that you'd rather build it in a template than inline in the action. For the full algorithm, see the [Jx Components and Layouts guide](/docs/jx_components).

### The `Vary: Accept` Gotcha

Here's the trap. The action above returns two completely different responses for the same URL, depending on the `Accept` header. But caches - the browser's, a CDN's, an intermediate proxy's - look up cached responses by *URL*, not by URL plus headers. Without further instruction, a cache that has stored the HTML version may serve it back for a JSON request, or vice versa.

The fix is the `Vary` header. `Vary: Accept` tells caches "this response varies based on the `Accept` header; treat the (URL, Accept) pair as the cache key, not the URL alone." Set it with an `after` callback so it covers both branches:

```python
class CardController(AppController):
    after = {"do": "set_vary", "only": "show"}

    def set_vary(self):
        self.response.set_vary("Accept")

    def show(self):
        ...
```

You only need this on actions that actually serve more than one format. A pure HTML controller doesn't need it; neither does a pure JSON controller. The header costs you nothing if you set it everywhere, but the after-callback approach keeps the wiring obvious - it's right next to the action that needs it.

:::warning | Easy to miss in development
Without `Vary: Accept`, your dev environment usually works fine: you're hitting the server with a single client at a time and the cache is empty. The bug shows up in production behind a CDN, where one user's HTML response gets served to another user's JSON request. Set the header when you write the dual-format action, not when you debug it.
:::

### When This Pattern Stops Fitting

Branching on `self.request.format` is the right move when one or two HTML actions also need to answer JSON. It stops being the right move when you're writing a controller that's mostly JSON - you end up with `if self.request.format == "json"` at the top of every action, the cookie machinery is doing work no JSON client needs, and `validate_form`'s "re-render the form template" reaction makes no sense for an API.

At that point, the controller wants to be a JSON-only controller: cookies disabled, validation handled inline, errors rendered as JSON instead of HTML. That's a different shape with its own conventions, covered separately.

---

## HTTP Caching with `fresh_when`

A page that doesn't change often is a page worth not re-rendering. `fresh_when` is the controller-level tool for turning an action into a *conditional GET*: the browser asks "do you have a newer version than what I already have?", and if the answer is no, the server returns `304 Not Modified` with an empty body.

### Conditional GETs in One Paragraph

Every response can carry an `ETag` (a fingerprint of the body) and a `Last-Modified` header (the timestamp of the most recent change). On the next request, the browser sends those values back in `If-None-Match` and `If-Modified-Since`. If the values still match what the server would produce, the server skips rendering and returns 304 with no body. The browser shows the version it already has cached. The user sees the same page; the server did almost no work.

`fresh_when` sets those headers for you, and tells the framework "if the request already matches, return 304 and discard whatever I rendered."

### Single Records

Pass a model object with an `updated_at` attribute:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.response.fresh_when(self.card)
```

That's the whole API for the common case. The `updated_at` timestamp drives both the ETag and the `Last-Modified` header, so the next time the same client requests the same card, it gets a `304 Not Modified` until somebody saves the card and the timestamp moves.

You don't have to skip the rest of the action when the response is fresh; the framework will do that for you. After the action returns, Proper checks the cache headers, and if the client already has the latest version, it discards the rendered body and sends `304` with no body.

### Collections

Pass an iterable of objects (a Peewee query is an iterable) and Proper picks the maximum `updated_at` across them:

```python
def index(self):
    self.cards = Card.select().order_by(Card.created_at.desc())
    self.response.fresh_when(self.cards)
```

The implication: the response is "fresh" until *any* card in the list changes. If your collection is paginated, only the items on the current page are considered, which is usually what you want.

### The `strong` and `public` Options

By default, `fresh_when` produces a *weak* ETag and a *private* cache directive. Both defaults are usually right for HTML pages.

```python
self.response.fresh_when(self.card, strong=True, public=True)
```

- `strong=True` produces a strong validator. Use it when you serve byte-for-byte identical responses every time and want range requests or some CDNs to work. For HTML pages that include a session-dependent layout, leave it weak.
- `public=True` allows shared proxy caches (a CDN, a corporate proxy) to store the response. Default to *private* unless you've thought through what's in the body - personalized pages, anything behind login, anything that varies by cookie should stay private.

You can also set the values explicitly:

```python
self.response.fresh_when(etag="v1-abc123", last_modified=some_datetime)
```

That form is useful when the "freshness key" isn't a model timestamp - for example, a page that depends on a config file's mtime.

### When to Reach for It (and When Not To)

`fresh_when` pays off when:

- The action's body is expensive to render (lots of templates, lots of queries).
- The same client revisits the same URL often.
- The data behind the page changes infrequently.

It doesn't pay off when:

- The page is already fast, or rarely re-requested.
- Every visit is from a different client (no cached version on the other end).
- The body changes on every request (a feed with timestamps, a page with the current user's avatar baked in).

The cost of `fresh_when` is small but not zero: you still query the database to get `updated_at`, and you may render the page only to throw the body away. If you're not seeing 304s in the access log after adding it, take it back out.

---

## Raising HTTP Errors

When a request can't be satisfied, the controller raises an exception that maps to an HTTP status code. The framework catches it, looks for a registered handler, and renders the matching error page.

```python
from proper.errors import NotFound, Forbidden

def set_card(self):
    card_id = self.params.get("card_id", "")
    self.card = Card.get_or_none(id=int(card_id))
    if not self.card:
        raise NotFound

def update(self):
    if not self.card.editable_by(current.user):
        raise Forbidden("You don't have permission to edit this card")
```

Every error class accepts an optional message string. The message is shown on the rendered error page in development; in production, you usually want a generic page regardless of message.

### The Error Classes

All of these live in `proper.errors` and inherit from `proper.errors.HTTPError`:

| Class                    | Status | When to use                                          |
| ------------------------ | ------ | ---------------------------------------------------- |
| `BadRequest`             | 400    | Malformed request data.                              |
| `Unauthorized`           | 401    | The request needs authentication and has none.       |
| `Forbidden`              | 403    | Authenticated, but not allowed.                      |
| `NotFound`               | 404    | The record or page doesn't exist.                    |
| `MethodNotAllowed`       | 405    | Wrong HTTP method (raised by the router).            |
| `NotAcceptable`          | 406    | No representation matches the `Accept` header.       |
| `Conflict`               | 409    | Conflicting state - typically a duplicate.           |
| `Gone`                   | 410    | Permanently removed; do not link to it again.        |
| `UnprocessableEntity`    | 422    | The syntax is fine but the semantics aren't.         |
| `TooManyRequests`        | 429    | Rate limit exceeded (raised by `RateLimiting`).      |
| `InternalServerError`    | 500    | Something went wrong on the server.                  |

A handful of more specialized subclasses exist (`InvalidOrigin` is a `Forbidden`, `MatchNotFound` is a `NotFound`, and so on). The full list is in `proper.errors`.

:::tip | 401 vs. 403
The HTTP spec is finicky about these two: 401 means "you didn't authenticate," 403 means "you authenticated, and you still can't have it." A logged-out visitor hitting `/admin` should usually be redirected to the login page, not get a 401. Reach for `Forbidden` when a logged-in user is trying to do something their role doesn't allow.
:::

### Raising vs. Returning a Manual Response

Two paths produce an error response from a controller. Both are fine; they're for different situations.

**Raise** when something goes wrong from somewhere deep in the call stack - inside a `before` callback, inside a helper, inside a model method. The exception unwinds the stack, halting any callbacks that were about to run, and lets the framework's error handling take over:

```python
def set_card(self):
    self.card = Card.get_or_none(id=int(self.params.get("card_id", "")))
    if not self.card:
        raise NotFound
```

**Return** a manual response when the action wants tight control over the body - for example, a JSON API that returns a structured error payload:

```python
def show(self):
    self.card = Card.get_or_none(self.params["card_id"])
    if not self.card:
        return self.render(json={"error": "card not found"}, status=404)
    return self.render(json={"id": self.card.id, "title": self.card.title})
```

The rule of thumb: raise from setup code, return from action code. If you find yourself returning a manual error response from a `before` callback, you probably wanted to raise instead.

### Custom Error Handlers

By default, an unhandled `NotFound` renders Proper's built-in 404 page. To replace that with your own, register a handler with `@router.error`:

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

When a `NotFound` is raised anywhere during request processing, the framework instantiates `PublicController`, sets up `self.request` and `self.response`, calls `not_found`, and renders the matching template (`public/not_found.jx` in this case). `@router.error(Exception)` is the catch-all - any unhandled exception lands there.

### The `_not_found` Trick

Notice the second decorator on each method:

```python
@router.error(errors.NotFound)
@router.get("_not_found")
def not_found(self):
    pass
```

`@router.get("_not_found")` mounts the same method at a regular URL, so during development you can visit `/_not_found` in the browser and see exactly what your error page looks like - styles, layout, copy, the lot - without having to provoke a real 404. The `@router.error` decorator wires up the production path; the `@router.get` decorator wires up the preview.

The leading underscore is a convention: it keeps the URL out of the way of real routes and signals "this is a developer affordance, not a public page." You can still link to it from a dev-only debug menu if that helps.

:::note | Use whatever path you like
There's nothing magic about `_not_found` and `_error`. If you prefer `/dev/404` and `/dev/500`, just put those strings in the `@router.get(...)` decorators. The error handler is wired up by `@router.error(...)`, not by the URL.
:::
