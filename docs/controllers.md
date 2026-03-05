title: Controllers
----

# Controllers

A controller is responsible for processing the request and generating the appropriate output.
They are defined in individual files (one for each class) inside the `myapp/controllers/` folder (or a subfolder).
They must be imported in the `myapp/controllers/__init__.py` file.

A controller is generated as part of a resource. A resource is generated using the command `proper g resource NAME`.
See the output of `proper g resource --help` to see all the options.

It is customary for controllers that:

* Their names are **singular** ("PhotoController" instead of "PhotosController")
* Their names are suffixed with "Controller"
* Their files are named with the same name in snake-case, including the "controller" suffix. File: `thing_controller.py`, class: `ThingController`.

Every controller must inherit from `AppController`, which itself inherits from
`Controller` plus any concerns:

```python
from proper import Controller
from proper.concerns import OriginProtection, RateLimiting
from .concerns.security_headers import SecurityHeaders


class AppController(
    Controller,
    OriginProtection,
    RateLimiting,
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


## 1. The Core Principle: Everything is CRUD

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


### 1.1 ID parameter

The `:card_id` parameter is auto-generated from the singular of the snake-cased controller name (after removing the "Controller" suffix).

Examples:

* `CardController` -> `card_id`
* `UserPhotoController` -> `user_photo_id`

It can also be manually specified with the `pk` argument. For example, `router.resource("cards", pk="object")` will use the `object_id` parameter (instead of `card_id`) in their URLs.

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


### 1.2 Manually defined URLs

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


## 2. The Generated Controller

When you run `proper g resource Card title:str body:text`, Proper generates a controller with the full CRUD pattern. Here's what it looks like (simplified):

```python {title="myapp/controllers/card_controller.py"}
from proper.errors import NotFound
from proper.status import unprocessable

from ..forms.card import CardForm
from ..models import Card
from ..router import router
from .app_controller import AppController


@router.resource("cards")
class CardController(AppController):
    before = {"do": "set_card", "exclude": ("index", "new", "create")}

    def index(self):
        self.cards = Card.select()

    def show(self):
        pass    # card is loaded by the before callback

    def new(self):
        self.form = CardForm()

    def edit(self):
        self.form = CardForm(object=self.card)

    def create(self):
        self.form = CardForm(self.params)
        if self.form.is_invalid:
            return self.render("pages/card/new.jinja", status=unprocessable)

        card = self.form.save()
        card.save()
        self.response.redirect_to(
            "Card.show",
            card_id=card.id,
            flash="Card was created",
        )

    def update(self):
        self.form = CardForm(self.params, object=self.card)
        if self.form.is_invalid:
            return self.render("pages/card/edit.jinja", status=unprocessable)

        card = self.form.save()
        card.save()
        self.response.redirect_to(
            "Card.show",
            card_id=self.card.id,
            flash="Card was updated",
        )

    def delete(self):
        if self.card:    # deleting twice does not fail
            self.card.delete_instance()
        self.response.redirect_to(
            "Card.index",
            flash="Card was deleted",
        )

    def set_card(self):
        card_id = self.params.get("card_id", "")
        if not card_id.isdigit():
            raise NotFound
        self.card = Card.get_or_none(int(card_id))
        if self.request.matched_action != "delete" and not self.card:
            raise NotFound
```

Key patterns to notice:

- The `before` callback `set_card` loads the record before `show`, `edit`, `update`, and `delete`. It is excluded from `index`, `new`, and `create` because those actions don't need an existing record.
- On `create` and `update`, if the form is invalid, the controller re-renders the form template with a `422 Unprocessable Entity` status instead of redirecting.
- After a successful create, update, or delete, the controller redirects with a flash message.
- The `delete` action checks `if self.card` to handle the case where someone deletes the same record twice (e.g., double-clicking the delete button).
- `form.save()` returns a model instance with validated data, but you still need to call `.save()` on the model to persist it to the database.


## 3. Parameters

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
            return self.render("pages/client/new.jinja", status=unprocessable)

        client = self.form.save()
        client.save()
        self.response.redirect_to(
            "Client.show",
            client_id=client.id,
            flash="Client was created",
        )
```

### 3.1 Params Quick Reference

```python
self.params                # MultiDict: merged query + form + route params
self.params.get("key")     # Value for key, or None
self.params["key"]         # Value for key (raises KeyError if missing)
self.params.getall("key")  # All values for key (HTML forms can send multiple)
```

Because `self.params` is a `MultiDict`, `self.params["key"]` returns the **last** value for that key, not the first. Use `self.params.getall("key")` when a form sends multiple values for the same name (e.g., checkboxes).

### 3.2 Accessing Sources Individually

If you need to distinguish where a parameter came from:

```python
self.request.query         # Query string params only (MultiDict)
self.request.form          # POST body params only (MultiDict, includes file uploads)
self.request.matched_params  # Route params only (dict)
```

### 3.3 Route Defaults

Routes can define default values that are available in the controller via `self.defaults`:

```python
# In the router:
@router.get("pages/:slug", defaults={"sidebar": True})
def show(self): ...

# In the controller:
self.defaults["sidebar"]   # True
```


## 4. Sessions

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


## 5. Rendering Responses

### 5.1 Implicit Template Rendering

If an action method returns `None` and doesn't set `response.body`, the framework
**automatically infers a template** from the controller's module path:

- `myapp.controllers.thing_controller` → `pages/thing/{action}.jinja`
- `myapp.controllers.admin.user_controller` → `pages/admin/user/{action}.jinja`

The inferred template is logged at DEBUG level: `[Controller.action] rendering inferred template: ...`

This means the simplest action is one that does nothing:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    # Automatically renders pages/controllers/card/show.jinja
```

### 5.2 Explicit Template Rendering

Use `self.render()` when you need to render a different template than the default, or when you need to set a custom status code:

```python
# Render a specific template
def create(self):
    self.form = CardForm(self.params)
    if self.form.is_invalid:
        # Re-render the "new" form template instead of the "create" template
        return self.render("pages/card/new.jinja", status=unprocessable)
```

The `render()` method returns a string that becomes the response body when returned from the action. You can also call it without returning — it sets the body directly.

### 5.3 JSON Responses

```python
def show(self):
    card = Card.get_by_id(self.params["card_id"])
    return self.render(json={"id": card.id, "title": card.title})
```

This sets the Content-Type to `application/json` and serializes the data using a custom encoder that handles `datetime` objects.

### 5.4 Plain Text Responses

```python
def healthcheck(self):
    return self.render(text="ok")
```

This sets the Content-Type to `text/plain`.

### 5.5 Setting a Custom Status

You can set the status in the response object:

```python
from proper import status

self.response.status = status.im_a_teapot
```

All render modes also accept a `status` parameter:

```python
return self.render("pages/card/new.jinja", status=unprocessable)
return self.render(json={"error": "not found"}, status=not_found)
return self.render(text="created", status=created)
```

Status codes are imported from `proper.status` as strings like `"422 Unprocessable Entity"`.

### 5.6 Return Values

If an action returns a value (any non-`None` value), that value becomes the response body directly:

```python
def show(self):
    return "Hello, world!"    # Sent as the response body
```

### 5.7 Template Variables

All instance attributes set on the controller are passed to the template as variables:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.related = Card.select().where(Card.category == self.card.category).limit(5)
    # {{ card }} and {{ related }} are now available in the template
```


## 6. Redirecting

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

### 6.1 Flash Messages

Flash messages are one-time messages that survive a single redirect. They are stored in the session and displayed on the next page load. You can set a flash message when redirecting:

```python
self.response.redirect_to(
    "Card.index",
    flash="Card was deleted",
)

self.response.redirect_to(
    "Session.new",
    flash="Try again in a few minutes.",
    flash_type="error",
)
```

The `flash_type` defaults to `"info"`. Common types are `"info"`, `"success"`, `"warning"`, and `"error"`.

You can also set flash messages directly without redirecting:

```python
self.response.flash.message("success", "Settings saved")
```

In your templates, flash messages are available as a list of `(type, message)` tuples via the session.


## 7. Raising HTTP Errors

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

### 7.1 Available Error Classes

| Class                         | Status Code | When to use
| ----------------------------- | ----------- | -----------
| `BadRequest`                  | 400         | Malformed request data
| `Unauthorized`                | 401         | Missing authentication
| `Forbidden`                   | 403         | Authenticated but not authorized
| `NotFound`                    | 404         | Record or page doesn't exist
| `MethodNotAllowed`            | 405         | Wrong HTTP method (raised by router)
| `Conflict`                    | 409         | Conflicting state (e.g., duplicate)
| `Gone`                        | 410         | Resource permanently removed
| `UnprocessableEntity`         | 422         | Valid syntax but semantic errors
| `TooManyRequests`             | 429         | Rate limit exceeded (raised by RateLimiting concern)

All error classes inherit from `proper.errors.HTTPError` and accept an optional message string.

### 7.2 Registering Error Handlers

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


## 8. HTTP Caching

Proper has built-in support for conditional GET requests using ETag and Last-Modified headers. This happens automatically in the dispatch flow: after calling an action, the framework checks if the response is "fresh" (the client already has the latest version). If so, it returns a `304 Not Modified` with an empty body instead of the full response.

### 8.1 fresh_when

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


## 9. The Request Object

Inside a controller, `self.request` gives you access to the full HTTP request. Here are the most commonly used properties:

```python
self.request.method           # HTTP method: "GET", "POST", etc.
self.request.path             # URL path: "/cards/42"
self.request.host             # Hostname: "example.com"
self.request.remote_ip        # Client IP address
self.request.user_agent       # User-Agent header string

self.request.query            # Query string params (MultiDict)
self.request.form             # Form body params (MultiDict, includes file uploads)
self.request.session          # Session data (DotDict, read-only side)
self.request.headers          # Request headers

self.request.matched_route    # The Route object that matched
self.request.matched_params   # Dict of extracted path parameters
self.request.matched_action   # Action name string (e.g., "show")
```

### 9.1 Cookies

```python
# Read an unsigned cookie
value = self.request.get_cookie("theme", default="light")

# Read a signed cookie (validates signature and optional max_age)
token = self.request.get_signed_cookie("_token", max_age=2592000)
```

### 9.2 Conditional Request Headers

These are used automatically by the caching system, but you can access them directly:

```python
self.request.if_none_match      # ETag values from If-None-Match header
self.request.if_modified_since  # datetime from If-Modified-Since header
```


## 10. The Response Object

Inside a controller, `self.response` gives you access to the outgoing HTTP response:

```python
self.response.status          # Status Code: 200 (OK)
self.response.body            # Response body (set by render or return value)
self.response.has_body        # True if body has been set (even to empty string)
self.response.mimetype        # Content-Type without charset
self.response.content_type    # Full Content-Type header
```

### 10.1 Setting Headers

```python
self.response.headers["X-Custom"] = "value"
self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
```

### 10.2 Setting Cookies

```python
self.response.set_cookie("theme", "dark", max_age=31536000, secure=True, httponly=True)
self.response.set_signed_cookie("_auth", token, max_age=2592000, httponly=True)
self.response.unset_cookie("old_cookie")
```

Cookies default to `samesite="Lax"`. Signed cookies use the app's secret key.

### 10.3 Cache Control

```python
self.response.set_cache_control("max-age=3600", "public")
self.response.set_cache_control("max-age=0", "private", "must-revalidate")
self.response.set_cache_control("max-age=31536000", "public", "immutable")
```

### 10.4 Sending Files

Use `self.response.send_file()` to send a file as the response. The mimetype is auto-detected from the filename:

```python
def download(self):
    self.response.send_file(
        "/path/to/report.pdf",
        as_attachment=True,              # Prompt download dialog
        download_name="Q4-Report.pdf",   # Override the filename
    )
```

In production, use the `x_sendfile_header` parameter to delegate file serving to nginx or Apache:

```python
self.response.send_file(
    filepath,
    x_sendfile_header="X-Accel-Redirect",    # nginx
)
```

### 10.5 Sending status

```python
from proper import status

self.response.status = status.im_a_teapot
```


## 11. Controller Callbacks

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
- Before callbacks run per-class in MRO order (parent to child); after callbacks run in reverse MRO order (child to parent)

### 11.1 `before` callback

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

### 11.2 `after` callback

You can also define action callbacks to run after a controller action has been executed with the `after` callback.

The `after` callbacks are similar to the `before` callbacks, but because the controller action has already been run they have access to the response data that's about to be sent to the client. A common use case is setting response headers:

```python
class SecurityHeaders(Concern):
    after = {"do": "_set_security_headers"}

    def _set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1", mode="block")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

::: warning
`after` callbacks are executed only after a successful controller action, and not if an exception is raised in the request cycle.
:::


### 11.3 Multiple callbacks

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

### 11.4 Inheritance

The `before` and `after` callbacks are always inherited and are not obscured by new declarations. Invoking an action in a controller with `before` callbacks defined, will first call any `before` callbacks defined in its parent classes, and then the ones defined in the controller class itself.

For example, if `AppController` has a `before` callback that checks authentication, and `CardController` has a `before` callback that loads a card, both will run — the authentication check first (from the parent), then the card loading (from the child).


## 12. Concerns

A controller concern is a mixin class that defines callbacks and methods that can be shared across multiple controllers. Concern classes inherit from `proper.Concern` and follow the same `before`/`after` callback pattern as controllers.

The convention is to declare them in the `myapp/controllers/concerns/` directory, one per file.

### 12.1 Writing a Concern

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

### 12.2 Built-in Concerns

These concerns are available from `proper.concerns`:

#### OriginProtection

Verifies that state-changing requests (POST, PATCH, PUT, DELETE) come from the same origin or a trusted origin. This is the modern CSRF protection approach that doesn't require tokens.

The verification algorithm:

1. Allow all GET, HEAD, OPTIONS, and QUERY requests (safe methods).
2. If neither `Sec-Fetch-Site` nor `Origin` headers are present, allow the request (not a browser request).
3. If the `Origin` header matches the `TRUSTED_ORIGINS` config, allow the request.
4. If `Sec-Fetch-Site` is `same-origin` or `none`, allow the request (modern browsers).
5. If the `Origin` host matches the request's `Host`, allow the request (HTTP or old browsers).
6. Otherwise, raise `InvalidOrigin` (403 Forbidden).

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
            flash_type="error",
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

#### SecurityHeaders

Sets security-related response headers as an `after` callback. This concern is defined in your app (not in the framework) so you can customize it:

```python {title="myapp/controllers/concerns/security_headers.py"}
from proper import Concern

class SecurityHeaders(Concern):
    after = {"do": "_set_security_headers"}

    def _set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1", mode="block")
        self.response.headers.setdefault("X-Download-Options", "noopen")
        self.response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

## 13. Adding More Actions

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
