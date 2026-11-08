---
title: API Reference
description: Reference: attributes and methods of Controller, App, Request and Response; other public exports; units; DotDict and MultiDict
last_verified: 2026-11-07
sources:
  - src/proper/controller/controller.py
  - src/proper/app.py
  - src/proper/core/request
  - src/proper/core/response
  - src/proper/helpers/dicts
  - src/proper/units.py
---

# API Reference

Read this to confirm an exact attribute, method or signature. The guides explain how to use them: [controllers.md](../controllers.md), [rendering.md](../rendering.md), [app.md](../app.md).

## Table of Contents

- [Controller](#controller)
- [App](#app)
- [Request](#request)
- [Response](#response)
- [Other Public Exports](#other-public-exports)
- [Units](#units)
- [Helper Types](#helper-types)


## Controller

The base class for all controllers. Accessed as `self` inside controller actions.

### Attributes

| Attribute  | Type       | Description                                         |
|------------|------------|-----------------------------------------------------|
| `request`  | `Request`  | The incoming HTTP request                           |
| `response` | `Response` | The outgoing HTTP response                          |

### Properties

| Property   | Type        | Description                                                                 |
|------------|-------------|-----------------------------------------------------------------------------|
| `app`      | `App`       | The application instance (shortcut for `self.request.app`)                  |
| `params`   | `MultiDict` | Merged query string + form body + route parameters. Route params win on conflict. |
| `defaults` | `dict`      | Default values defined on the matched route                                 |

### Methods

| Method   | Signature                                                    | Description                                                                                                  |
|----------|--------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `render` | `(name="", *, status=None, json=None, text=None, stream=None) -> str` | Render a template, JSON, plain text or Turbo Stream response (`stream`: one fragment or a list; sets the `text/vnd.turbo-stream.html` mimetype). Sets `response.body` and optionally `response.status`. |
| `redo`   | `(status=422) -> None`                                       | Re-render the form page for the current action by setting `self.response.body` directly. Maps `update` → `edit.jx`; any other action → `new.jx`. Use in `create`/`update` when `form.is_invalid`. |

### Callbacks

Callbacks are class attributes that control before/after hooks. See [concerns.md](../concerns.md#controller-callbacks) for full details.

| Attribute    | Type                   | Description                                                        |
|--------------|------------------------|--------------------------------------------------------------------|
| `before`     | `dict \| list[dict]`   | Before-action callbacks. Keys: `do`, `only`, `exclude`.            |
| `after`      | `dict \| list[dict]`   | After-action callbacks. Same keys as `before`.                     |
| `etag`       | `str`                  | Class attribute, `""` by default: a cache-key fragment that concerns extend with `super().etag` (pagination, locale, timezone). |

### Template Variables

Any attribute you set on `self` inside an action (e.g. `self.cards = Card.select()`) is automatically passed to the template as a variable (`{{ cards }}`).

### Implicit Rendering

If an action returns `None` and `response.body` is not set, the framework renders an inferred template at `views/{module}/{action}.jx`. Call `self.render()` only when you need a different template or a custom status.


## App

Accessed via `current.app` or directly from the app instance.

### Attributes

| Attribute        | Type                          | Description                                          |
|------------------|-------------------------------|------------------------------------------------------|
| `name`           | `str`                         | Application name derived from the root path          |
| `root_path`      | `Path`                        | Absolute path to the application package (`myapp/`)  |
| `views_path`     | `Path`                        | Path to views folder                                 |
| `config_path`    | `Path`                        | Path to config folder                                |
| `assets_path`    | `Path`                        | `assets/` folder at the project root (`root_path.parent / "assets"`) |
| `locales_path`   | `Path`                        | `config/locales/` inside the app package             |
| `storage_path`   | `Path`                        | `storage/` folder at the project root (`root_path.parent / "storage"`) |
| `router`         | `Router`                      | The application router instance                      |
| `config`         | `DotDict`                     | Configuration values, accessed as attributes         |
| `catalog`        | `proper.views.Catalog`        | The component catalog (see [jx_catalog.md](jx_catalog.md)) |
| `db`             | `dict[str, pw.Database]`      | Dictionary of Peewee database connections            |
| `queue`          | `Huey`                        | Task queue instance                                  |
| `cache`          | `BaseCache`                   | Cache backend instance                               |
| `mailer`         | `BaseMailer`                  | Default mailer backend instance                      |
| `mailers`        | `Mailers`                     | Mailer registry — `app.mailers[name]` selects a backend by config name |
| `auth`           | `Auth`                        | Auth instance (password hashing, token helpers)      |
| `i18n`           | `I18n \| None`                | Internationalization instance (`None` if not installed) |
| `cable`          | `BaseCable`                   | The cable of the channels: `Cable` with the channels addon; without it, a `BaseCable` that serves no WebSockets |
| `request_cls`    | `type[Request]`               | Request class used for creating request objects      |
| `response_cls`   | `type[Response]`              | Response class used for creating response objects    |
| `env`            | `str`                         | `APP_ENV`: `"dev"` (default), `"test"` or `"prod"` |
| `import_name`    | `str`                         | The package the app was built from                  |
| `max_threads`    | `int`                         | `MAX_THREADS`, or `min(32, cpu_count + 4)` when `0`  |
| `pipeline`       | `tuple[function, ...]`        | Class attribute: the request pipeline steps, in order |
| `tools`          | `tuple[module, ...]`          | Class attribute: the tool modules whose `setup(app)` runs at init |
| `CLI`            | `type`                        | The `proper` command class for this app             |

### Properties

| Property   | Type          | Description                                                                           |
|------------|---------------|---------------------------------------------------------------------------------------|
| `debug`    | `bool`        | Debug mode flag (read/write). Updates `config.DEBUG`, `router.debug`, and `catalog.auto_reload` |
| `routes`   | `list[Route]` | All registered routes (read-only)                                                     |

### Methods

| Method             | Signature                                                  | Description                                              |
|--------------------|------------------------------------------------------------|----------------------------------------------------------|
| `url_for`          | `(name, object=None, *, _anchor="", _full=False, **kw) -> str` | Generate URL for a named route. `_full=True` for absolute URLs. |
| `url_is`           | `(name, object=None, *, curr_url="", **kw) -> bool`       | Check if current URL matches a named route               |
| `url_startswith`   | `(name, object=None, *, curr_url="", **kw) -> bool`       | Check if current URL starts with a named route path      |
| `dumps`            | `(obj, salt=None, *, timed=True) -> str`                   | Serialize and sign a value with the newest secret key (the last in `SECRET_KEYS`). `timed=False`: no timestamp, same token every time, never expires |
| `loads`            | `(value, *, max_age=None, return_timestamp=False, salt=None, timed=True) -> Any` | Deserialize and verify a signed value. Tries all secret keys. Returns `None` if invalid, expired or undecodable. `timed=False` for `dumps(..., timed=False)` tokens (then `max_age`/`return_timestamp` raise `ValueError`). `return_timestamp=True` returns `(value, UTC datetime)` |
| `on_error`         | `(func) -> func`                                           | Decorator to register error handlers                     |
| `on_teardown`      | `(func) -> func`                                           | Decorator to register teardown handlers                  |
| `around_request`   | `(func) -> func`                                           | Decorator to register a function `func(request, response, call_next)` that wraps every request |
| `attachment_for`   | `(base_model_cls) -> type[_Attachment]`                    | Build an `Attachment` model subclass for the storage addon (memoized per app+base). Its `Reference` attribute is the model of the records that embed each attachment |
| `has_migrations_pending` | `() -> bool`                                         | Any migration under `db/<name>/` not applied to its database |
| `lower`            | `() -> None`                                               | Lower the dispatch decisions and compile every view; raises `LoweringError`, and `proper.views.CompileError` outside debug |
| `__call__`         | `(environ, start_response) -> Iterable[bytes]`             | The app is a WSGI callable |


## Request

Accessed via `current.request` or as `self.request` inside a controller. See also: [rendering.md](../rendering.md#request-and-response-objects) for quick usage examples.

### Attributes

| Attribute          | Type              | Description                                                    |
|--------------------|-------------------|----------------------------------------------------------------|
| `method`           | `str`             | HTTP method, after HEAD-to-GET and method override processing  |
| `request_method`   | `str`             | Original HTTP method as sent by the client                     |
| `path`             | `str`             | The request path                                               |
| `protocol`         | `str`             | `"http"` or `"https"` (respects `X-Forwarded-Proto` from a `TRUSTED_PROXIES` peer) |
| `host`             | `str`             | The host from the `Host` header (lowercased), else the address the server listens on (`SERVER_NAME`); the client chooses it: never build URLs sent to others from it |
| `port`             | `int`             | The port from the `Host` header, else the server's port; the protocol's default port without one |
| `content_type`     | `str \| None`     | The `Content-Type` header (`None` without one)                 |
| `content_length`   | `int`             | Body size from the `Content-Length` header (`0` without one)   |
| `headers`          | `MultiDict`       | HTTP request headers                                           |
| `body`             | `bytes`           | The raw request body (`b""` for GET and HEAD)                  |
| `form`             | `MultiDict`       | Parsed request body (form fields and uploaded files; the members of a JSON object) |
| `matched_route`    | `Route \| None`   | The route matched during routing                               |
| `matched_params`   | `dict \| None`    | Parameters extracted from the URL pattern                      |
| `matched_action`   | `str`             | The action name for the matched route (`""` before routing)    |
| `default_format`   | `str`             | Fallback format when accept parsing fails (default: `"html"`)  |
| `scheme`           | `str`             | `"http"`/`"https"` as the server saw it, before `X-Forwarded-Proto` |
| `server`           | `tuple[str, int \| None] \| None` | Address the request arrived at                     |
| `client`           | `tuple[str, int \| None] \| None` | Peer address and port                              |
| `http_version`     | `str`             | HTTP version (e.g. `"1.1"`)                                    |
| `server_software`  | `str`             | How the server names itself (e.g. `"bearings/0.1.0"`); `""` if unknown |

### Properties

| Property           | Type                       | Description                                                         |
|--------------------|----------------------------|---------------------------------------------------------------------|
| `app`              | `App`                      | The application instance                                            |
| `session`          | `dict`                     | Session data (read/write)                                           |
| `query`            | `MultiDict`                | Query string parameters                                             |
| `query_string`     | `str`                      | Raw query string                                                    |
| `url`              | `str`                      | The path and the query string (no scheme or host)                   |
| `flashes`          | `list[tuple[str, str]]`    | Flash messages stored in the session                                |
| `accept`           | `list[str]`                | MIME types from `Accept` header, sorted by quality (`q`, or `Q`: parameter names are case-insensitive; a malformed parameter or `q` is ignored) |
| `accept_encoding`  | `list[str]`                | Encodings from `Accept-Encoding`, sorted by quality                 |
| `accept_language`  | `list[str]`                | Languages from `Accept-Language`, sorted by quality                 |
| `cookies`          | `dict[str, str]`           | Parsed cookies                                                      |
| `cookie`           | `dict[str, str]`           | Alias for `cookies`                                                 |
| `date`             | `datetime \| None`         | Parsed `Date` header (RFC 9110 date forms only, else `None`)        |
| `default_port`     | `int`                      | Default port for the protocol (443 or 80)                           |
| `format`           | `str`                      | Response format from `Accept` header (e.g. `"html"`, `"json"`)     |
| `forwarded`        | `list[dict[str, str]]`     | Parsed `Forwarded` header                                           |
| `host_with_port`   | `str`                      | `host:port` (omits port if default; an IPv6 host in brackets: `[::1]:8080`) |
| `if_none_match`    | `list[str]`                | ETags from `If-None-Match` header                                   |
| `if_modified_since`| `datetime \| None`         | Parsed `If-Modified-Since` header (RFC 9110 date forms only, else `None`) |
| `is_delete`        | `bool`                     | `True` if method is DELETE                                          |
| `is_get`           | `bool`                     | `True` if method is GET                                             |
| `is_head`          | `bool`                     | `True` if original method is HEAD                                   |
| `is_patch`         | `bool`                     | `True` if method is PATCH                                           |
| `is_post`          | `bool`                     | `True` if method is POST                                            |
| `is_put`           | `bool`                     | `True` if method is PUT                                             |
| `is_secure`        | `bool`                     | `True` if protocol is HTTPS                                        |
| `is_ssl`           | `bool`                     | Alias for `is_secure`                                               |
| `is_xhr`           | `bool`                     | `True` if `X-Requested-With` is `"XMLHttpRequest"`                 |
| `port_is_default`  | `bool`                     | `True` if port is the default for the protocol                     |
| `port_string`      | `str`                      | `":port"` or `""` if port is default                               |
| `remote_ip`        | `str`                      | Client IP. From a `TRUSTED_PROXIES` peer: `X-Forwarded-For`, else `Forwarded` (both read from the right, skipping trusted proxies), else `X-Real-IP`. Otherwise the peer's address. An `X-Forwarded-For` or `Forwarded` address loses its port and brackets, and `::ffff:1.2.3.4` becomes `1.2.3.4` |
| `turbo_frame`      | `str \| None`              | The `Turbo-Frame` header: id of the frame being updated, `None` for a full-page request |
| `turbo_stream`     | `bool`                     | `True` when `Accept` includes `text/vnd.turbo-stream.html` |
| `request_id`       | `str`                      | The `X-Request-ID` header, keeping only `[A-Za-z0-9_@-]` and at most 200 characters; if missing or empty after that, a new UUID4. Sent back in the response's `X-Request-ID` header (error responses too) |
| `user_agent`       | `str \| None`              | Value of the `User-Agent` header                                    |

### Methods

| Method              | Signature                                                                       | Description                          |
|---------------------|---------------------------------------------------------------------------------|--------------------------------------|
| `get_url`           | `(include_query=True) -> str`                                                   | The path, with the query string unless `include_query=False` (no scheme or host) |
| `get_cookie`        | `(name, default=None) -> str \| None`                                           | Get a cookie value by name           |
| `get_signed_cookie` | `(name, default=None, *, salt="cookie", max_age=None) -> str \| Any`            | Get and verify a signed cookie value |


### Cookies

```python
# Read an unsigned cookie
value = self.request.get_cookie("theme", default="light")

# Read a signed cookie (validates signature and optional max_age)
token = self.request.get_signed_cookie("_token", max_age=2592000)
```

### Conditional Request Headers

These are used automatically by the caching system, but you can access them directly:

```python
self.request.if_none_match      # ETag values from If-None-Match header
self.request.if_modified_since  # datetime from If-Modified-Since header
```


## Response

Accessed via `current.response` or as `self.response` inside a controller. See also: [rendering.md](../rendering.md#request-and-response-objects) for quick usage examples.

### Attributes

| Attribute          | Type                   | Description                                            |
|--------------------|------------------------|--------------------------------------------------------|
| `status`           | `int`                  | HTTP status code (default: 200)                        |
| `body`             | `str \| bytes \| Iterable[bytes] \| None` | Response body content (`send_file` sets a file wrapper) |
| `flash`            | `FlashMessages`        | Flash messages manager; callable: `flash(category, message)`; `flash.flashes` is the list |
| `exclude_headers`  | `dict[int, tuple[str, ...]]` | Class attribute: headers dropped for a 204 and a 304 |
| `headers`          | `ResponseHeadersDict`  | Response headers                                       |
| `cookies`          | `dict[str, Morsel]`    | Cookies to send in the response                        |
| `default_mimetype` | `str`                  | Default MIME type (default: `"text/html"`)             |
| `default_charset`  | `str`                  | Default charset (default: `"utf-8"`)                   |
| `max_cookie_size`  | `int`                  | Maximum cookie size in bytes (default: 4093)           |
| `disable_cookies`  | `bool`                 | Disable cookie sending (default: `False`)              |

### Properties

| Property       | Type      | Description                           |
|----------------|-----------|---------------------------------------|
| `app`          | `App`     | The application instance              |
| `session`      | `dict`    | Session data (read/write)             |
| `error`        | `Exception \| None` | The exception that caused this response (read/write). Setting it drops the body and its headers, sets `status` from the error (500 by default) and copies the error's `headers` |
| `has_body`     | `bool`    | `True` if the response has a body     |
| `status_code`  | `int`     | Alias for `status`                    |

### Header Properties

All of these are read/write except where noted. Getters return the header as sent. The setters of `cache_control`, `content_encoding` and `vary` take a list of values (`response.vary = ["Accept"]`), `expires` and `last_modified` a `datetime`, `retry_after` an `int`; the `set_*` methods below take the same as positional arguments, and `None` (or no arguments) deletes the header.

| Property           | Type                | Description                         |
|--------------------|---------------------|-------------------------------------|
| `accept_ranges`    | `str \| None`       | `Accept-Ranges` header              |
| `cache_control`    | `list[str] \| None` | `Cache-Control` directives          |
| `content_encoding` | `str \| None`       | `Content-Encoding` header           |
| `content_length`   | `int \| None`       | `Content-Length` header              |
| `content_location` | `str \| None`       | `Content-Location` header           |
| `content_range`    | `str \| None`       | `Content-Range` header (read-only, use `set_content_range`) |
| `content_type`     | `str \| None`       | Full `Content-Type` header          |
| `mimetype`         | `str`               | MIME type portion of `Content-Type`  |
| `charset`          | `str`               | Charset portion of `Content-Type`   |
| `etag`             | `str \| None`       | `ETag` header (read-only, use `set_etag` to write) |
| `expires`          | `str \| None`       | `Expires` header                    |
| `last_modified`    | `datetime \| None`  | `Last-Modified` header              |
| `location`         | `str \| None`       | `Location` header                   |
| `retry_after`      | `str \| None`       | `Retry-After` header                |
| `vary`             | `str \| None`       | `Vary` header                       |

### Methods

| Method               | Signature                                                                                                  | Description                                              |
|----------------------|------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| `redirect_to`        | `(url_or_route, obj=None, *, flash=None, flash_cat="positive", status=303, **kw) -> None`                 | Redirect to a URL or named route with optional flash     |
| `fresh_when`         | `(objects=None, *, etag=None, last_modified=None, strong=False, public=False, request=None) -> bool`       | Set cache headers and return whether the response is fresh |
| `is_fresh`           | `(request=None) -> bool`                                                                                   | Check if response is fresh based on request cache headers |
| `send_file`          | `(path, *, mimetype=None, as_attachment=False, download_name=None, x_sendfile_header="") -> None`          | Send a file as the response body                         |
| `set_cookie`         | `(name, value="", *, max_age=None, path="/", domain=None, secure=False, httponly=False, samesite="Lax", comment="", signed=False, salt="cookie") -> None` | Set a response cookie |
| `unset_cookie`       | `(name, *, path="/", domain=None) -> None`                                                                                           | Delete a cookie                                          |
| `set_signed_cookie`  | `(name, value="", *, max_age=None, path="/", domain=None, secure=False, httponly=False, samesite="Lax", comment="", salt="cookie") -> None` | Set a cryptographically signed cookie |
| `set_etag`           | `(val, *, strong=False) -> None`                                                                           | Set the `ETag` header (weak or strong)                   |
| `set_cache_control`  | `(*directives) -> None`                                                                                    | Set `Cache-Control` directives                           |
| `set_content_type`   | `(mimetype, charset) -> None`                                                                              | Set the `Content-Type` header                            |
| `set_last_modified`  | `(dt) -> None`                                                                                             | Set the `Last-Modified` header                           |
| `set_expires`        | `(dt) -> None`                                                                                             | Set the `Expires` header                                 |
| `set_location`       | `(url) -> None`                                                                                            | Set the `Location` header                                |
| `set_content_length` | `(num) -> None`                                                                                            | Set the `Content-Length` header                           |
| `set_vary`           | `(*names) -> None`                                                                                         | Set the `Vary` header                                    |
| `set_accept_ranges`  | `(unit="bytes") -> None`                                                                                   | Set the `Accept-Ranges` header                           |
| `set_content_range`  | `(unit="bytes", *, start=None, end=None, size=None) -> None`                                               | Set the `Content-Range` header                           |
| `set_retry_after`    | `(num) -> None`                                                                                            | Set the `Retry-After` header                             |
| `set_content_encoding` | `(*values) -> None`                                                                                      | Set the `Content-Encoding` header                        |
| `set_content_location` | `(url) -> None`                                                                                          | Set the `Content-Location` header                        |
| `prepare`            | `(request=None) -> tuple[int, list[tuple[str, str]], bytes \| Iterable[bytes]]`                             | Status, headers and body ready for the server (an empty body for `HEAD`) |
| `get_headers_list`   | `() -> list[tuple[str, str]]`                                                                              | Headers and cookies as `(name, value)` pairs             |

### Setting Headers

```python
self.response.headers["X-Custom"] = "value"
self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
```

### Setting Cookies

```python
self.response.set_cookie("theme", "dark", max_age=31536000, secure=True, httponly=True)
self.response.set_signed_cookie("_auth", token, max_age=2592000, httponly=True)
self.response.unset_cookie("old_cookie")
```

Cookies default to `samesite="Lax"`. Signed cookies are signed with the newest secret key; every key in `SECRET_KEYS` is accepted when reading.

### Cache Control

```python
self.response.set_cache_control("max-age=3600", "public")
self.response.set_cache_control("max-age=0", "private", "must-revalidate")
self.response.set_cache_control("max-age=31536000", "public", "immutable")
```

### Sending Files

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

### Setting Status

```python
from proper import status

self.response.status = status.im_a_teapot
```


## Other Public Exports

Everything below is importable from `proper` (e.g., `from proper import Concern`) unless its row names another module. `proper` also exports `Request`, `Response`, `TestClient`, `CIMultiDict`, and `turbo_frame`/`turbo_stream` (from `proper.turbo`, which also has `TURBO_STREAM_MIME`).

### Concern

Base class for controller concerns (mixins with callbacks). See [concerns.md](../concerns.md#concerns).

```python
from proper import Concern

class TeamScoped(Concern):
    def load_team(self):
        ...
```

### Routing

See [routing.md](../routing.md) and [urls.md](../urls.md) for full details.

| Symbol         | Description                                                    |
|----------------|----------------------------------------------------------------|
| `Router`       | Main router — registers routes via `resource()`, `get()`, `post()`, ..., `static()`, `add_route()` |
| `ScopedRouter` | Nested router returned by `scope()` blocks                     |
| `Route`        | A single registered route (name, path, method, controller, action) |
| `StaticRoute`  | Route for serving static assets                                |

### Models

See [models.md](../models.md) for full details.

| Symbol         | Description                                                              |
|----------------|--------------------------------------------------------------------------|
| `ProperModel`  | Base Peewee model with scope support and token generation methods        |
| `scope`        | Decorator that tags a classmethod as a chainable query scope             |
| `ScopedSelect` | The `Select` subclass returned by scoped queries; propagates scopes through chained method calls (rarely used directly). |
| `JSONField`    | Backwards compatibility only: use `pw.JSONField` (also re-exported from `proper`) |
| `run_seeds`    | `from proper.models import run_seeds`: `(name="", db="main") -> bool`, the `proper db seed` runner |

### Channel

WebSocket channel base class. See [channels.md](../channels.md) for full details.

| Method             | Description                                      |
|--------------------|--------------------------------------------------|
| `subscribed()`     | Called when a client subscribes — override to set up streams |
| `unsubscribed()`   | Called on disconnect — override for cleanup       |
| `stream_from(stream_name)`| Subscribe this connection to a broadcast stream   |
| `stop_stream_from(stream_name)` | Unsubscribe from a stream                  |
| `stop_all_streams()` | Unsubscribe from all streams                    |
| `send(data)`       | Send data to this connection                     |
| `broadcast(stream, data)` | Broadcast data to all subscribers of a stream |
| `reject()`         | Reject the subscription                         |
| `track(stream_name, data=None, *, key=None)` / `untrack(stream_name)` / `update_presence(data)` | Presence in a stream |
| `find_user(user_id)` / `find_session()` | Resolve the connection's user and session; `AppChannel` defines them |

Attributes: `app`, `params` (dict), `user_id`; properties `channel_name`, `authenticated`, `request` (the handshake). Class attributes `Session`, `auth_cookie_name` (`"_auth"`), `auth_cookie_salt`. `proper.channels` also exports `ActionError`, `BaseCable`, `Cable`, `RedisCable` and `CABLE_SALT`.

### Emails

These symbols are exported from `proper.emails`, **not** the top-level `proper`. Import via `from proper.emails import EmailMessage`. See [emails.md](../emails.md) for full details.

| Symbol             | Module                  | Description                                              |
|--------------------|-------------------------|----------------------------------------------------------|
| `EmailMessage`     | `proper.emails`         | Compose an email (subject, to, body, attachments)        |
| `EmailMessageDict` | `proper.emails`         | Serialized form of `EmailMessage` (the value mailers send) |
| `EmailAttachment`  | `proper.emails`         | TypedDict for file attachments                           |
| `EmailAlternative` | `proper.emails`         | TypedDict for alternative content parts                  |
| `BaseMailer`       | `proper.emails`         | Abstract mailer backend                                  |
| `SMTPMailer`       | `proper.emails`         | Send via SMTP                                            |
| `ToConsoleMailer`  | `proper.emails`         | Print emails to stdout (development)                     |
| `ToMemoryMailer`   | `proper.emails`         | Store emails in a list (testing)                         |
| `EmailTemplateNotFound` | `proper.emails`    | `LookupError` raised when an email has no body and no template |

### Helpers

Utility functions and classes available from `proper`.

| Symbol            | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `DotDict`         | Dict subclass with attribute-style access (`d.key`)            |
| `MultiDict`       | Dict that supports multiple values per key (query/form params) |
| `CIMultiDict`     | Case-insensitive `MultiDict` (request headers)                 |
| `JSONField`       | Backwards compatibility only: use `pw.JSONField`                |
| `make_list`       | `from proper.helpers import make_list`: wrap a value in a list if it isn't one already (a tuple becomes a list) |

### Global Context

`current` (`from proper import current`): `current.app`, `current.request`, `current.response`, and `current.user`, `current.auth_session`, `current.locale`, `current.timezone` (`None` when their addon is not installed). See [app.md](../app.md#global-context).


## Units

Proper provides readable constants for sizes and durations, used throughout configuration:

```python
from proper.units import MB, GB, SECONDS, MINUTES, HOURS, DAYS, WEEKS
```

**Size:**

| Constant | Value   |
|----------|---------|
| `B`      | 1       |
| `KB`     | 1024    |
| `MB`     | 1048576 |
| `GB`     | 2^30    |
| `TB`     | 2^40    |

**Time** (in seconds):

| Constant           | Value     |
|--------------------|-----------|
| `SECOND` / `SECONDS` | 1      |
| `MINUTE` / `MINUTES` | 60     |
| `HOUR` / `HOURS`     | 3600   |
| `DAY` / `DAYS`       | 86400  |
| `WEEK` / `WEEKS`     | 604800 |
| `MONTH` / `MONTHS`   | 2592000 (30 days) |
| `YEAR` / `YEARS`     | 31536000 (365 days) |

There's also `to_seconds(**kwargs)` which converts `timedelta` keyword arguments:

```python
from proper.units import to_seconds

to_seconds(hours=2, minutes=30)  # 9000
```


## Helper Types

### DotDict

A dict subclass that allows attribute-style access. Used for `app.config` (the sessions are plain dicts):

```python
from proper.helpers import DotDict

d = DotDict({"name": "Alice", "settings": {"theme": "dark"}})
d.name              # "Alice"
d.settings.theme    # "dark" (nested dicts are also DotDicts)
d.missing           # AttributeError (d["missing"] raises KeyError)
```

`update()` does deep merging — nested dicts are merged recursively rather than replaced.

### MultiDict

A dict-like type that handles multiple values per key. Used for `request.form` and `request.query`:

```python
# Given ?color=red&color=blue
request.query.get("color")           # "blue" (last value)
request.query.getall("color")        # ["red", "blue"]
request.query.get("color", index=0)  # "red" (first value)
request.query.get("count", type=int) # type-casts the value
request.query["color"]               # "blue": [] and pop() give the last value
```

`set(key, values)` replaces every value of a key, `append(key, value)` adds one, `extend(key, values)` several; `getall(key, type=int)` drops the values the cast rejects.
