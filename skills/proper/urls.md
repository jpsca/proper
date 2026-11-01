---
title: URL Generation
description: `url_for` with placeholders, objects, defaults, query parameters, anchors and absolute URLs; `url_is` / `url_startswith`; asset URLs
last_verified: 2026-10-31
sources:
  - src/proper/router
  - src/proper/helpers/html.py
---

# URL Generation

Building URLs from route names, in Python (`app.url_for`, `redirect_to`) and in templates. Defining the routes is in [routing.md](routing.md).

## Table of Contents

- [Named Routes and URL Generation](#named-routes-and-url-generation)
- [Assets](#assets)


## Named Routes and URL Generation

Every route has a name. For resource routes, the name is `ControllerName.action` (without the "Controller" suffix). For individual routes, it is derived from the method's qualified name, or you can set it explicitly with the `name` parameter.

### Basic Usage

Use `app.url_for()` to generate the URL for a named route:

```python
app.url_for("Photo.index")         # /photos
app.url_for("Photo.new")           # /photos/new
```

### Passing Placeholder Values

For routes with placeholders, pass the values as keyword arguments:

```python
class PostController(AppController):
    @router.get("posts/:post_id<int>/:post_slug")
    def show(self):
        ...

app.url_for("Post.show", post_id=42, post_slug="hello-world")
# /posts/42/hello-world
```

### Passing an Object

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

### Placeholders with Defaults

A route's `defaults=` (or its scope's) with the name of a path or host placeholder is what `url_for` uses when that placeholder isn't given:

```python
@router.get("docs/:lang<en|es>/:slug", defaults={"lang": "en"})
def show(self): ...

app.url_for("Doc.show", slug="intro")   # /docs/en/intro
```

- Order: `url_for` argument > attribute of the object > default. A `None` argument or attribute takes the default.
- A default can be a function without arguments, called on each `url_for` (`lambda: current.account.id`). If it returns `None`, `url_for` raises `MissingRouteParameter`, as it does without a default. In tasks and emails there is no `current.account`, so give the value there.
- Defaults that aren't placeholders (`{"sidebar": True}`) never go into the URL or the query string.
- A default that isn't a placeholder is never called, even if it's a function or a class: it reaches `self.defaults` as it is. A misspelled placeholder name shows up in `proper check` as a missing placeholder.
- On a match, the value in the URL is the one in `self.params`. `self.defaults` is the dict as declared.
- `proper check` doesn't report a placeholder with a default as missing.

### Extra Keyword Arguments Become Query Parameters

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

### Value Checks and Percent-Encoding

- Each placeholder value must match its format as a whole, or `url_for` raises `BadRoutePlaceholder` (`"42abc"` is not an `<int>`; `"a/b"` is not a default `:slug`, only a `<path>` takes a `/`).
- Path values, and the route's own text (`/über/:id` → `/%C3%BCber/42`), are percent-encoded, except `/` (only a format that accepts `/`, such as `<path>`, takes one in a value) and ``:@!$&'()*+,;=``, which a path allows as they are. `url_for("Tag.show", tag="a b?")` → `/tags/a%20b%3F`; `token=":signed_id"` stays `:signed_id` (for JS URL templates).
- Query keys and values are encoded like a form (`urlencode`, from `str()` for non-strings): `url_for("Post.index", q="a&b c")` → `/posts?q=a%26b+c`; `next="/admin/x"` → `?next=%2Fadmin%2Fx`.
- Pass raw values, not already-encoded ones (`"a%20b"` becomes `a%2520b`).
- A value that makes a `.` or `..` path segment raises `BadRoutePlaceholder` (`name="."` or `".."` for `/files/:name`, `page="a/../b"` for `<path>`): clients remove those segments (RFC 3986 §5.2.4), and `%2e` is a dot to browsers, so encoding can't help. `"..."` or `".env"` are fine.

### URL Anchors

Use the `_anchor` keyword argument to append a `#fragment` to the URL. It is percent-encoded like a path value (`?` also stays): `_anchor="a b#c"` → `#a%20b%23c`. Pass it unencoded.

```python
app.url_for("Post.show", post_id=42, post_slug="hello", _anchor="comments")
# /posts/42/hello#comments
```

### Absolute URLs

Use `_full=True` to generate absolute URLs (includes protocol and host). Useful for email links:

```python
app.url_for("Post.show", post, _full=True)
# https://example.com/posts/42/hello-world
```

A host placeholder value (`host=":username.myapp.com"`) may have only letters, digits and `-._~`; any other character raises `BadRoutePlaceholder` with `_full=True`, whatever the placeholder's format.

### `url_is` and `url_startswith`

These helpers check whether the current request URL matches a named route. They are useful for highlighting the active link in navigation menus:

```python
app.url_is("Photo.index")
```

Returns `True` if the current request path matches `/photos` exactly. Only paths are compared, percent-decoded: the query string, the `#fragment` and trailing slashes are ignored, and so are query kwargs (`url_is("Photo.index", page=2)` is `True` on `/photos`). An explicit `curr_url` is a percent-encoded URL, as in a link; `request.path` is already decoded, so to compare with it leave `curr_url` out.

```python
app.url_startswith("Photo.index")
```

Returns `True` if the current request path starts with `/photos`, by whole segments (`/photography` does not start with `/photo`). This is useful for highlighting a parent navigation item when any child page is active. Every path starts with a route at `/`; use `url_is` for a "Home" link.

Both helpers accept the same arguments as `url_for()` (objects, keyword arguments) for routes with placeholders:

```python
app.url_is("Post.show", post)
app.url_startswith("Post.show", post)
```

### Absolute Paths as Passthrough

If you pass a string starting with `/` to `url_for()`, it is returned as-is without any lookup:

```python
app.url_for("/some/hardcoded/path")   # /some/hardcoded/path
```


## Assets

Proper includes a built-in `StaticFilesController` for serving files from the `assets/` folder at the project root. The route is configured in your application's `router.py`:

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

The fingerprint is a SHA-256 of the file's modification time, inserted before the extension (`app-<64 hex chars>.css`); a file that doesn't exist under `assets/` gets its URL without one. The cache headers and `X-Sendfile` are in [app.md](app.md#static-assets).
