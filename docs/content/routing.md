---
title: Routing
description: |
  The router matches incoming requests to controller methods and powers URL generation throughout your app. This guide covers resource routes, individual routes, scopes, host-based routing, redirects, error handlers, URL helpers, and how to inspect every route from the CLI.
number_headers: true
---

# Routing

In this guide, you will learn how Proper's router decides which controller method handles each incoming request, and how to generate URLs for those routes from your code and templates.

After reading this guide, you will know:

- How Proper matches a request to a controller method.
- How to define resource routes, individual routes, scopes, and host-based routes.
- How to generate URLs from route names with `url_for`.
- How redirects, error handlers, and build-only routes fit in.
- How to inspect every route in your app from the CLI.

---

## The Purpose of Routing

The router sits at the front of every request. When a browser asks for `GET /photos/42`, the router's job is to look at that request and decide which method on which controller should handle it. Once a route matches, the controller takes over to produce the response.

In Proper, routes are defined as decorators on controller classes, or on individual methods inside them. There is no central list of every route in your application; you write the route once, next to the code that handles it.

```python
# myapp/controllers/photo_controller.py
from ..router import router
from .app_controller import AppController


@router.resource("photos")
class PhotoController(AppController):
    def index(self): ...
    def show(self): ...
```

That's enough. The class is decorated, and the matching CRUD actions become routes. There is no separate routes file to keep in sync.

### Where Routes Live

A route is registered the moment its decorator runs. When Python imports a controller module, the `@router.resource(...)` decorator on the class executes and adds the routes to to the shared `Router` instance. You can also decorate individual methods with `@router.get(...)`, `@router.post(...)`, etc. to do the same. There is no separate registration step.

Two pieces are involved at boot:

1. `myapp/router.py` holds the `Router` instance and any routes that don't belong to a controller - assets, root-level redirects, and `scope(...)` declarations for namespaced sections. A fresh app's `router.py` looks like this:

```python
# myapp/router.py
"""
Routes without a controller.
Other routes are defined as decorators and mounted when
the controllers are imported.
"""
from .main import app


router = app.router

# Assets
router.static(app.config.ASSETS_URL, root=app.assets_path, name="assets")

# Root-level assets
router.get("favicon.ico", redirect="/assets/favicon.ico")
router.get("robots.txt", redirect="/assets/robots.txt")
router.get("humans.txt", redirect="/assets/humans.txt")
```

2. Controllers, in turn, import this `router` and decorate their classes, or individual methods, with it. The decorator runs at import time, which is what registers the route. Controllers are loaded at app startup via `myapp/controllers/__init__.py`, so the decorators fire automatically as the app boots.

:::tip
The `proper g` generators handle the wiring for you: new controllers are added to `controllers/__init__.py` automatically, and the routes register themselves through the decorators.

You'll only edit `router.py` by hand for assets, redirects, or a new `scope(...)`.
:::

### Match Order

Routes are matched **top to bottom**. The first route that matches the request method, host, and path wins.

This matters when two routes could plausibly match the same URL. Placeholders are greedy: a generic `:username` will happily capture the digits `42`. To make a more specific route win, register it first.

```python
class UserController(AppController):
    @router.get("users/:user_id<int>")    # numeric ids only
    def show(self): ...

    @router.get("users/:username")        # anything else
    def show_by_name(self): ...
```

For `GET /users/42`, the first route matches because `42` satisfies `<int>`, and registration order settles the tie. Reverse the two decorators and `:username` would swallow the `42`, dispatching to `show_by_name` instead.

You don't have to think about this for resource routes - Proper orders the seven CRUD routes correctly for you. The rule mostly bites when you write several placeholder routes by hand against the same prefix.

If a request matches no route at all, Proper returns a 404, which you can customize. See [Error Handler Routes](#error-handler-routes).

---

## Resource Routes

The most common way to define routes is with `@router.resource()`. It takes a URL prefix and produces the seven RESTful CRUD routes pointing at the matching methods on the class:

```python
@router.resource("photos")
class PhotoController(AppController):
    def index(self): ...    # GET    /photos
    def new(self): ...      # GET    /photos/new
    def create(self): ...   # POST   /photos
    def show(self): ...     # GET    /photos/:photo_id
    def edit(self): ...     # GET    /photos/:photo_id/edit
    def update(self): ...   # PATCH  /photos/:photo_id  (and PUT)
    def delete(self): ...   # DELETE /photos/:photo_id
```

Seven actions cover the lifecycle of a typical resource: list it, show one, render forms to create or edit, accept the submissions, and delete. If your application keeps to this shape, almost all of your routes will be a single `@router.resource(...)` line per controller.

### Only Defined Actions Get Routes

You don't have to implement all seven actions. Proper inspects the class and only creates routes for methods that actually exist:

```python
@router.resource("articles")
class ArticleController(AppController):
    def index(self): ...
    def show(self): ...
    # No new/create/edit/update/delete - only the two GET routes are registered.
```

This is the natural way to mark a resource as read-only. There's no separate `only=` or `except=` parameter; the methods you write are the routes you get.

### PATCH and PUT Both Map to `update`

The `update` action is reachable via either `PATCH` or `PUT`. PATCH is the preferred verb for partial updates and is what HTML forms use via [method override](#method-override). PUT is accepted because some HTTP clients still send it.

You only define `update` once. Both verbs route to it.

### Route Names

Every route gets a name automatically. Resource route names follow a fixed pattern:

```
<ControllerName-without-suffix>.<action>
```

So a `PhotoController` with all seven actions produces:

| Method | Path                       | Name           |
|--------|----------------------------|----------------|
| GET    | `/photos`                  | `Photo.index`  |
| GET    | `/photos/new`              | `Photo.new`    |
| POST   | `/photos`                  | `Photo.create` |
| GET    | `/photos/:photo_id`        | `Photo.show`   |
| GET    | `/photos/:photo_id/edit`   | `Photo.edit`   |
| PATCH  | `/photos/:photo_id`        | `Photo.update` |
| PUT    | `/photos/:photo_id`        | `Photo.update` |
| DELETE | `/photos/:photo_id`        | `Photo.delete` |

You'll use these names with `url_for` to generate URLs. See [URL Generation](#url-generation).

When a controller lives in a subfolder under `controllers/`, the route name picks up a colon-separated namespace prefix derived from the folder names:

| Controller location                           | Route name           |
|-----------------------------------------------|----------------------|
| `controllers/photo_controller.py`             | `Photo.show`         |
| `controllers/admin/user_controller.py`        | `Admin:User.show`    |
| `controllers/api/v1/user_controller.py`       | `Api:V1:User.show`   |

Pass the full name (prefix included) to `url_for`: `app.url_for("Admin:User.show", user)`.

### Custom Primary Key

By default, the placeholder for the resource's id is derived from the controller name: `PhotoController` gets `:photo_id`, `CommentController` gets `:comment_id`. Change it with the `pk=` parameter:

```python
@router.resource("photos", pk="uuid")
class PhotoController(AppController):
    def show(self): ...     # GET /photos/:uuid
```

You can also constrain the format with angle brackets:

```python
@router.resource("photos", pk="uuid<[a-f0-9-]+>")
class PhotoController(AppController):
    def show(self): ...     # GET /photos/:uuid (only matches hex + dashes)
```

The same format-constraint syntax works on any placeholder. See [Path Placeholders](#path-placeholders-and-format-constraints).

### Singleton Resources

Some resources only have one instance per user, per request, or per app: a profile, an account, an inbox. There's no need for an id in the URL. Use `pk=None`:

```python
@router.resource("profile", pk=None)
class ProfileController(AppController):
    def new(self): ...      # GET    /profile/new
    def create(self): ...   # POST   /profile
    def show(self): ...     # GET    /profile
    def edit(self): ...     # GET    /profile/edit
    def update(self): ...   # PATCH  /profile
    def delete(self): ...   # DELETE /profile
```

There's no `index` action for a singleton; there's only one of it, so listing makes no sense.

### The "new at root" Convention

When a controller defines `new` but is missing the action that would normally occupy the resource root, Proper mounts `new` at the root path instead of `/new`. This is the natural shape for sign-up forms and similar one-page resources.

The rules:

- For group resources: when `index` is missing, `new` mounts at `/resource-name`.
- For singleton resources: when `show` is missing, `new` mounts at `/resource-name`.

```python
@router.resource("signup")
class SignupController(AppController):
    def new(self): ...      # GET  /signup     (not /signup/new - there's no index)
    def create(self): ...   # POST /signup
```

The form *is* the landing page, so it gets the friendly URL.

---

## Individual Routes

When a route doesn't fit the CRUD shape - a one-off page, a callback URL, a non-RESTful action - define it directly with an HTTP method decorator on the controller method.

```python
class ItemController(AppController):
    @router.get("items/:item_id")
    def show(self): ...

    @router.post("items")
    def create(self): ...

    @router.get("items/search")
    def search(self): ...
```

Use resource routes when you can. Reach for individual routes when you must.

### The HTTP Method Decorators

Proper provides one decorator per HTTP method:

```
router.get      router.post     router.put
router.patch    router.delete   router.options
router.query
```

`router.query` registers a `QUERY` request. See [The `QUERY` Method](#the-query-method) for what that is and when to use it.

### Path Placeholders and Format Constraints

Placeholders are prefixed with `:` and capture a single URL segment. By default they match anything except a slash:

```python
@router.get("posts/:slug")
def show(self): ...    # matches /posts/hello-world, /posts/42, /posts/anything
```

To restrict what a placeholder matches, add a format constraint in angle brackets:

| Format     | Matches                                | Type cast |
|------------|----------------------------------------|-----------|
| (none)     | Anything except slashes                | `str`     |
| `<int>`    | Integers only (`[0-9]+`)               | `int`     |
| `<float>`  | Floats only (`[0-9]+\.[0-9]+`)         | `float`   |
| `<path>`   | Anything, *including* slashes          | `str`     |
| `<regex>`  | Custom regular expression              | `str`     |

The `<int>` and `<float>` forms cast the captured value to the matching Python type. The others pass it through as a string.

```python
# Only matches integers; value is cast to int
@router.get("posts/:post_id<int>")
def show(self): ...

# Only matches floats; value is cast to float
@router.get("temperature/:temp<float>")
def show(self): ...

# Matches everything including slashes - useful for file paths or nested docs
@router.get("docs/:page<path>")
def show(self): ...

# Custom regex: only two-letter language codes from a fixed set
@router.get("docs/:lang<en|es|pt>/:page")
def show(self): ...

# Custom regex: a date-like path
@router.get("archive/:year<\\d{4}>/:month<\\d{2}>/:day<\\d{2}>")
def show(self): ...
```

Captured values arrive in the controller as `self.params`. See the [Controllers guide](/docs/controllers) for how to read them.

### Custom Route Names

By default, the route name is `<Controller>.<action>` (e.g., `Item.show`). Override it with `name=`:

```python
@router.get("sign-in", name="login")
def new(self): ...
```

Then `app.url_for("login")` returns `/sign-in`. Custom names are most useful when the URL doesn't reflect the action's purpose, or when you want to keep a stable name across a refactor.

### Route Defaults

Sometimes you want to register the same controller method at multiple URLs but pass slightly different context. The `defaults=` parameter merges fixed values into the route's params:

```python
class PageController(AppController):
    @router.get("pages/:slug", defaults={"sidebar": True})
    def show(self): ...

    @router.get("docs/:slug", defaults={"sidebar": False})
    def show_docs(self): ...
```

Inside the controller, `self.defaults["sidebar"]` reflects whichever route matched. Defaults are useful when you don't want this kind of branching to leak into the URL or the database.

---

## Scopes

Scopes group routes under a shared URL prefix. They're how you carve out an `/admin` panel, version an API at `/api/v1`, or namespace any section of the app.

```python
admin = router.scope("admin")

class AdminDashboardController(AppController):
    @admin.get("dashboard")
    def index(self): ...       # GET /admin/dashboard

    @admin.get("settings")
    def settings(self): ...    # GET /admin/settings
```

`admin` is a child router. Anything you register through it is automatically prefixed with `/admin`.

### Scoped Resource Routes

`@scope.resource(...)` works exactly like `@router.resource(...)`, with the prefix added:

```python
admin = router.scope("admin")

@admin.resource("users")
class AdminUserController(AppController):
    def index(self): ...    # GET    /admin/users
    def show(self): ...     # GET    /admin/users/:admin_user_id
    def edit(self): ...     # GET    /admin/users/:admin_user_id/edit
    def update(self): ...   # PATCH  /admin/users/:admin_user_id
    def delete(self): ...   # DELETE /admin/users/:admin_user_id
```

Notice the placeholder is `:admin_user_id`, derived from the controller name (`AdminUserController`), not from the URL prefix.

If you'd prefer a shorter placeholder, put the controller in a subfolder instead. A `controllers/admin/user_controller.py` with `class UserController` produces `:user_id` (from the class name) and the namespaced route name `Admin:User.show` (from the folder). Pick whichever pattern reads better in your codebase.

### Nested Scopes

Scopes are themselves routers, so you can nest them. The child inherits the parent's prefix:

```python
api = router.scope("api")
v1 = api.scope("v1")
v2 = api.scope("v2")

class ItemController(AppController):
    @v1.get("items")
    def index_v1(self): ...    # GET /api/v1/items

    @v2.get("items")
    def index_v2(self): ...    # GET /api/v2/items
```

Use this for API versioning, or anywhere a deeper hierarchy reads naturally.

### Scopes with Placeholders

The scope prefix can contain placeholders, with the same format-constraint syntax as paths:

```python
tenant = router.scope("org/:org_id<int>")

class ProjectController(AppController):
    @tenant.get("projects")
    def index(self): ...    # GET /org/:org_id/projects
```

This is the natural shape for multi-tenant apps where every URL carries the tenant id.

---

## Host-Based Routing

Routes can be restricted to a specific host or hostname pattern. This lets you serve different content on different subdomains, or split an API away from a marketing site that lives in the same code base.

```python
class ApiController(AppController):
    @router.get("users", host="api.example.com")
    def index(self): ...    # only matches when Host: api.example.com
```

A request to `/users` on `www.example.com` will not match this route.

### Host Placeholders

The `host` parameter accepts placeholders, with the same syntax as paths. This is how you extract a dynamic subdomain:

```python
# Match language subdomains: en.example.com, es.example.com, pt.example.com
class DocsController(AppController):
    @router.get("docs", host=":lang<en|es|pt>.example.com")
    def index(self): ...

# Match user subdomains: alice.myapp.com, bob.myapp.com, ...
class ProfileController(AppController):
    @router.get("", host=":username.myapp.com")
    def show(self): ...
```

Placeholders captured from the host arrive in `self.params` alongside path placeholders.

### Scopes with Host

`router.scope(...)` accepts `host=` too. This applies the host constraint to every route registered through the scope:

```python
api = router.scope("", host="api.example.com")

class ApiUserController(AppController):
    @api.get("users")
    def index(self): ...           # GET /users on api.example.com only

    @api.get("users/:id")
    def show(self): ...            # GET /users/:id on api.example.com only
```

You can combine `host` with a path prefix:

```python
api_v1 = router.scope("v1", host="api.example.com")

class ApiItemController(AppController):
    @api_v1.get("items")
    def index(self): ...           # GET /v1/items on api.example.com
```

### Host Inheritance in Nested Scopes

Nested scopes inherit the parent's host unless they explicitly override it:

```python
api = router.scope("api", host="api.example.com")
internal = api.scope("internal", host="internal.example.com")

class StatusController(AppController):
    @internal.get("status")
    def index(self): ...    # GET /api/internal/status on internal.example.com
```

The path prefix continues to compose (`/api` + `/internal`) while the host is replaced.

---

## Redirects, Errors, and Build-Only Routes

Not every route dispatches to a controller. Three special shapes handle other use cases.

### Redirect Routes

A route can redirect to another URL instead of running a handler. This is useful for aliasing old URLs, mapping root-level files to the assets folder, or keeping a vanity URL working after a refactor:

```python
# Redirect root-level files to the assets folder
router.get("favicon.ico", redirect="/assets/favicon.ico")
router.get("robots.txt", redirect="/assets/robots.txt")
router.get("humans.txt", redirect="/assets/humans.txt")

# Redirect an old URL to a new one
router.get("old-blog", redirect="/posts")
```

By default, redirects use status code `307 Temporary Redirect`. Use `redirect_status=` for a permanent redirect:

```python
from proper import status

router.get("old-blog", redirect="/posts", redirect_status=status.moved_permanently)
```

Redirects can preserve placeholder values from the matched URL into the redirect target:

```python
# /articles/42 redirects to /posts/42
router.get("articles/:id", redirect="/posts/{id}")
```

Only `router.get()` and `router.options()` accept the `redirect` parameter. POST, PUT, PATCH, and DELETE routes do not - silently redirecting a write is rarely what you want.

### Error Handler Routes

You can register a controller method to handle a specific exception class. When that exception is raised anywhere during request processing, Proper instantiates the controller and calls the registered method instead of falling back to the generic error page:

```python
from proper import errors

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

Two decorators are stacked here intentionally:

- `@router.error(...)` registers the method as a handler for that exception.
- `@router.get("_not_found")` adds a route so you can preview the error page in development by visiting the URL directly. The leading underscore is a convention to keep the preview path out of the way.

Any exception class works - the built-in HTTP errors, your own subclasses, plain `Exception` for a catch-all.

### Build-Only Routes

A route with no handler and no `redirect=` is a "build-only" route. It will never match a request, but it can still be used with `url_for` to produce a URL string. This is useful when you need a stable name for a path that's actually handled outside Proper - an OAuth callback, a static file served by your reverse proxy, or anything generated externally:

```python
router.get("external/callback", name="oauth_callback")

# Later, in a controller or template:
app.url_for("oauth_callback")   # /external/callback
```

Build-only routes give you the same naming benefits (refactor the URL, keep the name) for paths Proper doesn't actually serve.

---

## Method Override

HTML forms only support GET and POST. To send PUT, PATCH, DELETE, or QUERY from a browser, Proper accepts a method override on a POST request. The override is read from any of:

- An `X-HTTP-Method-Override` header.
- A `_method` parameter in the query string.
- A `_method` field in the form body.

The most common form is a hidden input:

```html
<form action="/photos/42" method="post">
    <input type="hidden" name="_method" value="DELETE">
    <button type="submit">Delete Photo</button>
</form>
```

For an update form, use `PATCH`:

```html
<form action="/photos/42" method="post">
    <input type="hidden" name="_method" value="PATCH">
    <!-- form fields here -->
    <button type="submit">Save</button>
</form>
```

The override happens before route matching. By the time the router runs, the request looks exactly as if the browser had sent the overridden method directly. You don't have to special-case anything in the controller.

POST is the only method that can be overridden, and only to PUT, PATCH, DELETE, or QUERY.

---

## URL Generation

Hard-coded URLs in templates and controllers are a maintenance trap: change the route, find every reference. Proper avoids that with named routes and `url_for`.

### `app.url_for` Basics

Pass the route's name to get its URL:

```python
app.url_for("Photo.index")   # /photos
app.url_for("Photo.new")     # /photos/new
```

Resource route names are `Controller.action` (without the `Controller` suffix). Individual routes use the same shape unless you override with `name=`.

In Jx templates, `url_for` is a global - call it without any prefix:

```html
<a href="{{ url_for('Photo.index') }}">All photos</a>
```

### Passing Placeholder Values

For routes with placeholders, supply the values as keyword arguments:

```python
class PostController(AppController):
    @router.get("posts/:post_id<int>/:post_slug")
    def show(self):
        ...

app.url_for("Post.show", post_id=42, post_slug="hello-world")
# /posts/42/hello-world
```

### Passing an Object

Instead of typing out each placeholder, you can pass an object as the second positional argument. Proper extracts placeholder values from the object's attributes:

```python
# post.post_id = 42, post.post_slug = "hello-world"
app.url_for("Post.show", post)
# /posts/42/hello-world
```

For convenience, if the object doesn't have an attribute matching the *full* placeholder name (e.g., `post_id`), Proper also looks for the version without the snake-cased controller prefix (e.g., `id`). That means a normal model object works directly:

```python
# post.id = 42, post.slug = "hello-world"
app.url_for("Post.show", post)
# /posts/42/hello-world
```

This is the form you'll use in templates 90% of the time:

```html
<a href="{{ url_for('Post.show', post) }}">{{ post.title }}</a>
```

### Extra Keyword Arguments Become Query Parameters

Any keyword argument that isn't a placeholder is appended as a query string parameter:

```python
app.url_for("Post.index")                       # /posts
app.url_for("Post.index", page=2)               # /posts?page=2
app.url_for("Post.index", page=2, sort="date")  # /posts?page=2&sort=date
```

Path placeholders and query parameters mix freely:

```python
app.url_for("Post.show", post_id=42, post_slug="hello", ref="twitter")
# /posts/42/hello?ref=twitter
```

### `_anchor` and `_full`

`_anchor=` appends a `#fragment` to the URL:

```python
app.url_for("Post.show", post_id=42, post_slug="hello", _anchor="comments")
# /posts/42/hello#comments
```

`_full=True` returns an absolute URL with protocol and host. Use this when the URL will leave the request - emails, RSS feeds, third-party callbacks:

```python
app.url_for("Post.show", post, _full=True)
# https://example.com/posts/42/hello-world
```

### Active-Link Helpers: `url_is` and `url_startswith`

Two helpers check whether the *current* request matches a named route. They take the same arguments as `url_for`:

```python
app.url_is("Photo.index")
# True if the current path is /photos
```

`url_startswith` is the same idea, but matches any path that starts with the route's URL. It's handy for highlighting a parent navigation item when any of its children is active:

```python
app.url_startswith("Photo.index")
# True for /photos, /photos/42, /photos/42/edit, ...
```

Both helpers also accept objects and keyword arguments for routes with placeholders:

```python
app.url_is("Post.show", post)
app.url_startswith("Post.show", post)
```

A common pattern in templates:

```html
<a href="{{ url_for('Photo.index') }}"
   class="{{ 'active' if url_startswith('Photo.index') else '' }}">
   Photos
</a>
```

### Passthrough for Hardcoded Paths

If you pass a string that already starts with `/`, `url_for` returns it unchanged:

```python
app.url_for("/some/hardcoded/path")   # /some/hardcoded/path
```

This is occasionally useful in templates that accept either a route name or a literal path; you can call `url_for` unconditionally and let it decide.

---

## Assets

Proper ships with a built-in `StaticFilesController` for serving files from your application's `assets/` folder. The route is registered in `router.py`:

```python
router.static(app.config.ASSETS_URL, root=app.assets_path, name="assets")
```

Generate URLs to specific files with `url_for`:

```python
app.url_for("assets", file="app.css")
# /assets/app-a1b2c3d4e5f6...css

app.url_for("assets", file="images/logo.png")
# /assets/images/logo-e5f6a1b2c3d4...png
```

By default, asset URLs are *fingerprinted*: a hash derived from the file's last-modified time is inserted into the filename. This lets you set long-lived cache headers on assets while ensuring browsers fetch fresh versions whenever a file changes.

See the [Assets guide](/docs/assets) for the full story on how fingerprinting, the assets folder layout, and the build pipeline fit together.

---

## The QUERY Method

Alongside the standard methods, Proper supports the proposed [`QUERY` method](https://httpwg.org/http-extensions/draft-ietf-httpbis-safe-method-w-body.html). A QUERY request is like GET but allows a request body. It exists for the case where you need to send structured search criteria that don't fit cleanly into a URL's query string - think a search form with arrays of filters, or a complex JSON predicate.

```python
class SearchController(AppController):
    @router.query("search")
    def index(self): ...
```

QUERY must be idempotent (the same request must produce the same result), because caches are allowed to store the response keyed on the request body. Don't use it for actions with side effects.

Browsers can't send QUERY directly from a form. To trigger one from an HTML form, use [Method Override](#method-override) with `_method="QUERY"`.

---

## Inspecting Routes

The `proper routes` command prints a table of every route registered in your application:

```bash
❯ proper routes
```

```

Routes match in priority from top to bottom.
The rules that don't have a `to` property are build-only and never match.

       PATH                     TO                          NAME              HOST
       ------------------------ --------------------------- ----------------- ----
GET    /assets/:file<path>      StaticFilesController.show  assets            -
GET    /favicon.ico             ↪ /assets/favicon.ico       -                 -
GET    /robots.txt              ↪ /assets/robots.txt        -                 -
GET    /humans.txt              ↪ /assets/humans.txt        -                 -
GET    /photos                  PhotoController.index       Photo.index       -
GET    /photos/new              PhotoController.new         Photo.new         -
POST   /photos                  PhotoController.create      Photo.create      -
GET    /photos/:photo_id        PhotoController.show        Photo.show        -
GET    /photos/:photo_id/edit   PhotoController.edit        Photo.edit        -
PATCH  /photos/:photo_id        PhotoController.update      Photo.update      -
PUT    /photos/:photo_id        PhotoController.update      Photo.update      -
DELETE /photos/:photo_id        PhotoController.delete      Photo.delete      -
GET    /                        PublicController.index      Public.index      -
GET    /_not_found              PublicController.not_found  Public.not_found  -
GET    /_error                  PublicController.error      Public.error      -
```

The output is space-separated columns, not a pipe-delimited table: the method column has a blank header, and a row of dashes underlines each column. The example above is reproduced as the terminal actually prints it.

How to read it:

- The **PATH** column shows the URL pattern, including any format constraints.
- The **TO** column shows where the route dispatches. A normal route shows `Controller.action`; a controller in a subfolder under `controllers/` is prefixed with that folder path (e.g. `admin/UserController.show`). A redirect shows `↪ /target` so you can see at a glance which routes are redirects and where they go. A build-only route shows `-`.
- The **NAME** column is what you pass to `url_for`. Routes without a name (like redirects) show `-`.
- The **HOST** column shows any host constraint, or `-` if the route matches all hosts.

The output reflects exactly the order Proper uses for matching, so this is also the tool for debugging the [match order](#match-order) rule from §1: if a request is hitting the wrong route, find both candidates in the table and check which one comes first.
