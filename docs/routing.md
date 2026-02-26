title: Routing
----

# Routing

## 1. Routes

### 1.1 Resource Routes (CRUD)

The most common way to define routes in Proper is with the `@router.resource()` decorator on a controller class. This creates a full set of RESTful CRUD routes for the resource:

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

Only methods that exist on the class get routes. If your controller only defines `index` and `show`, only those two routes will be created. You don't need to define every action.

Note that both PATCH and PUT are routed to the `update` method. This means you can use either HTTP method to update a resource.

By default, the primary key placeholder is derived from the controller name: `PhotoController` gets `:photo_id`, `CommentController` gets `:comment_id`, etc.

#### Route Names

Each route is automatically assigned a name based on the controller name (without the "Controller" suffix) and the action:

Route                         | Name
----------------------------- | ------------------
GET    /photos                | Photo.index
GET    /photos/new            | Photo.new
POST   /photos                | Photo.create
GET    /photos/:photo_id      | Photo.show
GET    /photos/:photo_id/edit | Photo.edit
PATCH  /photos/:photo_id      | Photo.update
DELETE /photos/:photo_id      | Photo.delete

#### Custom Primary Key

You can change the primary key placeholder by passing the `pk` parameter:

```python
@router.resource("photos", pk="uuid")
class PhotoController(AppController):
    def show(self): ...     # GET /photos/:uuid
    def edit(self): ...     # GET /photos/:uuid/edit
    def update(self): ...   # PATCH /photos/:uuid
    def delete(self): ...   # DELETE /photos/:uuid
```

You can also use a format constraint on the custom key:

```python
@router.resource("photos", pk="uuid<[a-f0-9-]+>")
class PhotoController(AppController):
    def show(self): ...     # GET /photos/:uuid  (only matches hex + dashes)
```

#### Singleton Resources

Sometimes you have a resource that clients always look up without referencing an ID. For example, a user's own profile page. Use `pk=None` to create a set of CRUD routes without an `:id` placeholder:

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

Notice there is no `index` action for singleton resources, because there is only one.

Route                   | Name
----------------------- | ------------------
GET    /profile/new     | Profile.new
POST   /profile         | Profile.create
GET    /profile         | Profile.show
GET    /profile/edit    | Profile.edit
PATCH  /profile         | Profile.update
DELETE /profile         | Profile.delete


### 1.2 Individual Routes

When you need routes that don't fit the CRUD pattern, you can define them individually as decorators on controller methods. Prefer resource routes when possible, but individual routes are useful for one-off pages, custom actions, or non-RESTful endpoints.

The available HTTP method decorators are: `router.get()`, `router.post()`, `router.put()`, `router.delete()`, `router.patch()`, `router.options()`, and `router.query()`.

```python
class ItemController(AppController):
    @router.get("items/:item_id")
    def show(self): ...

    @router.post("items")
    def create(self): ...

    @router.get("items/search")
    def search(self): ...
```

#### Path Placeholders

Placeholders in the path are prefixed with `:` and capture a segment of the URL. By default, they match anything except slashes:

```python
@router.get("posts/:slug")
def show(self): ...        # matches /posts/hello-world, /posts/42, etc.
```

You can add a format constraint inside angle brackets to restrict what the placeholder matches:

| Format    | Matches                                  | Type cast |
|-----------|------------------------------------------|-----------|
| (none)    | Anything except slashes                  | `str`     |
| `<int>`   | Integers only (`[0-9]+`)                 | `int`     |
| `<float>` | Floats only (`[0-9]+\.[0-9]+`)           | `float`   |
| `<path>`  | Anything, *including* slashes            | `str`     |
| `<regex>` | Custom regular expression                | `str`     |

The `<int>` and `<float>` formats automatically cast the matched value to the corresponding Python type. All other formats pass the value as a string.

```python
# Only matches integers, value is cast to int
@router.get("posts/:post_id<int>")
def show(self): ...

# Only matches floats, value is cast to float
@router.get("temperature/:temp<float>")
def show(self): ...

# Matches everything including slashes, useful for file paths
@router.get("docs/:page<path>")
def show(self): ...

# Custom regex: only matches two-letter language codes
@router.get("docs/:lang<en|es|pt>/:page")
def show(self): ...

# Custom regex: date format
@router.get("archive/:year<\\d{4}>/:month<\\d{2}>/:day<\\d{2}>")
def show(self): ...
```

#### Custom Route Names

By default, the route name is derived from the controller and method name (e.g., `Item.show`). You can override this with the `name` parameter:

```python
@router.get("sign-in", name="login")
def new(self): ...
```

Then use `app.url_for("login")` to generate the URL.

#### Route Defaults

You can pass extra values to the controller via the `defaults` parameter. These values are merged into the route params and are accessible inside the controller via `self.defaults`:

```python
@router.get("pages/:slug", defaults={"sidebar": True})
def show(self): ...
```

Inside the controller, `self.defaults["sidebar"]` will be `True`.


### 1.3 Redirect Routes

You can define routes that redirect to another URL instead of dispatching to a controller. This is useful for aliasing old URLs, mapping root-level files, or creating vanity URLs:

```python
# Redirect root-level files to the assets folder
router.get("favicon.ico", redirect="/assets/favicon.ico")
router.get("robots.txt", redirect="/assets/robots.txt")
router.get("humans.txt", redirect="/assets/humans.txt")

# Redirect an old URL to a new one
router.get("old-blog", redirect="/posts")
```

By default, redirects use the status code `307 Temporary Redirect`. You can change this with the `redirect_status` parameter:

```python
from proper import status

# Permanent redirect (301)
router.get("old-blog", redirect="/posts", redirect_status=status.moved_permanently)
```

Redirect routes with placeholders work too. The placeholder values from the matched URL are interpolated into the redirect target:

```python
# /articles/42 redirects to /posts/42
router.get("articles/:id", redirect="/posts/{id}")
```

Only `router.get()` and `router.options()` support the `redirect` parameter. POST, PUT, PATCH, and DELETE routes do not.


### 1.4 Scoped Routes

Scopes let you group routes under a common URL prefix. This is useful for admin panels, API versioning, or any section of your app that shares a URL prefix:

```python
admin = router.scope("admin")

class AdminDashboardController(AppController):
    @admin.get("dashboard")
    def index(self): ...       # GET /admin/dashboard

    @admin.get("settings")
    def settings(self): ...    # GET /admin/settings
```

#### Scoped Resource Routes

You can use the `resource()` decorator on a scoped router to prefix all the CRUD routes:

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

#### Nested Scopes

Scopes can be nested. The inner scope inherits the prefix (and host, if set) from the outer scope:

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

#### Scopes with Placeholders

The scope prefix can contain placeholders, just like a route path:

```python
tenant = router.scope("org/:org_id<int>")

class ProjectController(AppController):
    @tenant.get("projects")
    def index(self): ...    # GET /org/:org_id/projects
```


### 1.5 Host-Based Routing

Both individual routes and scopes accept a `host` parameter to restrict matching to a specific hostname or subdomain. This is useful for serving different content on different subdomains, or separating an API from a marketing site:

```python
class ApiController(AppController):
    @router.get("users", host="api.example.com")
    def index(self): ...    # Only matches when Host is api.example.com
```

#### Host Placeholders

The `host` parameter supports the same placeholder syntax as paths. This lets you extract dynamic subdomains:

```python
# Match language subdomains: en.example.com, es.example.com, pt.example.com
class DocsController(AppController):
    @router.get("docs", host=":lang<en|es|pt>.example.com")
    def index(self): ...

# Match user subdomains: alice.myapp.com, bob.myapp.com
class ProfileController(AppController):
    @router.get("", host=":username.myapp.com")
    def show(self): ...
```

#### Scoped Host Routing

Use a scoped router with `host` to apply the same host constraint to a group of routes:

```python
api = router.scope("", host="api.example.com")

class ApiUserController(AppController):
    @api.get("users")
    def index(self): ...      # GET /users on api.example.com only

    @api.get("users/:id")
    def show(self): ...       # GET /users/:id on api.example.com only
```

You can combine `host` and `prefix` on a scope:

```python
api_v1 = router.scope("v1", host="api.example.com")

class ApiItemController(AppController):
    @api_v1.get("items")
    def index(self): ...      # GET /v1/items on api.example.com
```

When nesting scopes, the inner scope inherits the host from the outer scope unless it is explicitly overridden:

```python
api = router.scope("api", host="api.example.com")
internal = api.scope("internal", host="internal.example.com")

class StatusController(AppController):
    @internal.get("status")
    def index(self): ...      # GET /api/internal/status on internal.example.com
```


### 1.6 The QUERY Method

In addition to the standard HTTP methods, Proper supports `QUERY`. A QUERY request is like GET but allows a request body. This is useful when you need to send structured search criteria that don't fit cleanly in a query string:

```python
class SearchController(AppController):
    @router.query("search")
    def index(self): ...
```

QUERY requests must be idempotent because the body will be cached. Like GET, the CSRF token is not checked for QUERY requests.

To send a QUERY request from the browser, use the method override mechanism described below.


### 1.7 Error Handler Routes

You can register controller methods to handle specific exceptions. When that exception is raised during request processing, Proper will instantiate the controller and call the registered method instead of returning a generic error page:

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

The `@router.error()` decorator registers the handler, and the `@router.get()` decorator adds a route to preview that error page during development. You can stack both decorators as shown above.

Any exception class works, not just the built-in HTTP errors:

```python
@router.error(errors.NotFound)        # 404 pages
@router.error(errors.Forbidden)       # 403 pages
@router.error(Exception)              # Catch-all for 500 errors
```

### 1.8 Build-Only Routes

A route with no `to` handler and no `redirect` is a "build-only" route. It will never be matched during request routing, but it can be used with `url_for()` to generate URLs. This is useful when you need to generate URLs for an external service or a path handled outside of Proper:

```python
router.get("external/callback", name="oauth_callback")

# Later, in a controller:
app.url_for("oauth_callback")   # /external/callback
```


## 2. Method Override

HTML forms only support GET and POST. To send PUT, PATCH, or DELETE requests from a form, Proper uses a method override mechanism. When a POST request includes one of the following, the request method is transparently overridden:

- An `X-HTTP-Method-Override` header
- A `_method` parameter in the query string
- A `_method` field in the form body

The POST method can be overridden with: **PUT**, **PATCH**, **DELETE**, or **QUERY**.

In your HTML forms, add a hidden `_method` field:

```html
<form action="/photos/42" method="post">
    <input type="hidden" name="_method" value="DELETE">
    <button type="submit">Delete Photo</button>
</form>
```

Or to send a PUT/PATCH update:

```html
<form action="/photos/42" method="post">
    <input type="hidden" name="_method" value="PATCH">
    <!-- form fields here -->
    <button type="submit">Update Photo</button>
</form>
```

This override happens early in the middleware pipeline, before route matching, so the router sees the overridden method as if the browser had sent it directly.


## 3. Named Routes and URL Generation

Every route has a name. For resource routes, the name is `ControllerName.action` (without the "Controller" suffix). For individual routes, it is derived from the method's qualified name, or you can set it explicitly with the `name` parameter.

### 3.1 Basic Usage

Use `app.url_for()` to generate the URL for a named route:

```python
app.url_for("Photo.index")         # /photos
app.url_for("Photo.new")           # /photos/new
```

### 3.2 Passing Placeholder Values

For routes with placeholders, pass the values as keyword arguments:

```python
class PostController(AppController):
    @router.get("posts/:post_id<int>/:post_slug")
    def show(self):
        ...

app.url_for("Post.show", post_id=42, post_slug="hello-world")
# /posts/42/hello-world
```

### 3.3 Passing an Object

Instead of keyword arguments, you can pass an object. Proper will extract placeholder values from the object's attributes:

```python
# post.post_id = 42, post.post_slug = "hello-world"
app.url_for("Post.show", post)
# /posts/42/hello-world
```

For convenience, if the object doesn't have an attribute matching the full placeholder name (e.g., `post_id`), Proper also looks for the attribute without the snake_cased controller prefix (e.g., `id`). This means you can use your model objects directly:

```python
# post.id = 42, post.slug = "hello-world"
app.url_for("Post.show", post)
# /posts/42/hello-world
```

### 3.4 Extra Keyword Arguments Become Query Parameters

Any keyword arguments that don't match a placeholder in the route are appended as query string parameters:

```python
app.url_for("Post.index")                   # /posts
app.url_for("Post.index", page=2)            # /posts?page=2
app.url_for("Post.index", page=2, sort="date")  # /posts?page=2&sort=date
```

This works in combination with path placeholders too:

```python
app.url_for("Post.show", post_id=42, post_slug="hello", ref="twitter")
# /posts/42/hello?ref=twitter
```

### 3.5 URL Anchors

Use the `_anchor` keyword argument to append a `#fragment` to the URL:

```python
app.url_for("Post.show", post_id=42, post_slug="hello", _anchor="comments")
# /posts/42/hello#comments
```

### 3.6 `url_is` and `url_startswith`

These helpers check whether the current request URL matches a named route. They are useful for highlighting the active link in navigation menus:

```python
app.url_is("Photo.index")
```

Returns `True` if the current request path matches `/photos` exactly (ignoring trailing slashes).

```python
app.url_startswith("Photo.index")
```

Returns `True` if the current request path starts with `/photos`. This is useful for highlighting a parent navigation item when any child page is active.

Both helpers accept the same arguments as `url_for()` (objects, keyword arguments) for routes with placeholders:

```python
app.url_is("Post.show", post)
app.url_startswith("Post.show", post)
```

### 3.7 Absolute Paths as Passthrough

If you pass a string starting with `/` to `url_for()`, it is returned as-is without any lookup:

```python
app.url_for("/some/hardcoded/path")   # /some/hardcoded/path
```


## 4. Assets

Proper includes a built-in `StaticFilesController` for serving files from your `assets` folder. The route is configured in your application's `router.py`:

```python
router.static(app.config.ASSETS_URL, root=app.assets_path, name="assets")
```

Generate URLs to assets with `url_for`:

```python
app.url_for("assets", file="app.css")
# /assets/app-a1b2c3d4e5f6...css  (with fingerprint)

app.url_for("assets", file="images/logo.png")
# /assets/images/logo-e5f6a1b2c3d4...png  (with fingerprint)
```

By default, asset URLs are fingerprinted: a hash of the file's last modified time is inserted into the filename. This allows setting long-lived cache headers while ensuring browsers fetch new versions when files change.


## 5. Inspecting Routes

The command `proper routes` prints a table of all configured routes in your application:

```bash
proper routes
```

```
       | PATH                             | TO                               | NAME                  | HOST
------ | -------------------------------- | -------------------------------- | --------------------- | -----
GET    |  /assets/:file<path>             | StaticFilesController.show       | assets                | -
GET    |  /favicon.ico                    | -> /assets/favicon.ico           | -                     | -
GET    |  /robots.txt                     | -> /assets/robots.txt            | -                     | -
GET    |  /humans.txt                     | -> /assets/humans.txt            | -                     | -
GET    |  /photos                         | PhotoController.index            | Photo.index           | -
GET    |  /photos/new                     | PhotoController.new              | Photo.new             | -
POST   |  /photos                         | PhotoController.create           | Photo.create          | -
GET    |  /photos/:photo_id               | PhotoController.show             | Photo.show            | -
GET    |  /photos/:photo_id/edit          | PhotoController.edit             | Photo.edit            | -
PATCH  |  /photos/:photo_id              | PhotoController.update           | Photo.update          | -
PUT    |  /photos/:photo_id               | PhotoController.update           | Photo.update          | -
DELETE |  /photos/:photo_id               | PhotoController.delete           | Photo.delete          | -
GET    |  /                               | PublicController.index            | Public.index          | -
GET    |  /_not_found                     | PublicController.not_found        | Public.not_found      | -
GET    |  /_error                         | PublicController.error            | Public.error          | -
```

Redirect routes are shown with an arrow (`->`) pointing to the redirect target instead of a controller name. This makes it easy to see at a glance which routes are redirects and where they point to.
