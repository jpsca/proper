---
title: API
description: Quick reference for all public symbols exported by the proper package
last_verified: 2026-04-02
---

# API Reference

Quick reference for all public symbols in the `proper` package. Each entry links to the full documentation.

## Table of Contents

- [Controller](#controller)
- [App](#app)
- [Request](#request) (attributes, properties, methods, cookies, conditional headers)
- [Response](#response) (attributes, properties, header properties, methods, cookies, cache control, files, status)
- [Other Public Exports](#other-public-exports) (Concern, routing, models, channels, emails, helpers, global context, units)


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
| `render` | `(name="", *, status=None, json=None, text=None) -> str` | Render a template, JSON, or plain text response. Sets `response.body` and optionally `response.status`. |
| `redo`   | `(status=422) -> str`                                        | Re-render the form page for the current action. Maps `update` → `edit.jx`, `create` → `new.jx`. Use in `create`/`update` when `form.is_invalid`. |

### Callbacks

Callbacks are class attributes that control before/after hooks. See [Controllers — Callbacks](./controllers.md#11-controller-callbacks) for full details.

| Attribute    | Type                   | Description                                                        |
|--------------|------------------------|--------------------------------------------------------------------|
| `before`     | `dict \| list[dict]`   | Before-action callbacks. Keys: `do`, `only`, `exclude`.            |
| `after`      | `dict \| list[dict]`   | After-action callbacks. Same keys as `before`.                     |

### Template Variables

Any attribute you set on `self` inside an action (e.g. `self.cards = Card.select()`) is automatically passed to the template as a variable (`{{ cards }}`).

### Implicit Rendering

If an action returns `None` and `response.body` is not set, the framework renders an inferred template at `pages/{module}/{action}.jx`. Call `self.render()` only when you need a different template or a custom status.


## App

Accessed via `current.app` or directly from the app instance.

### Attributes

| Attribute        | Type                          | Description                                          |
|------------------|-------------------------------|------------------------------------------------------|
| `name`           | `str`                         | Application name derived from the root path          |
| `root_path`      | `Path`                        | Absolute path to the application root directory      |
| `views_path`     | `Path`                        | Path to views folder                                 |
| `config_path`    | `Path`                        | Path to config folder                                |
| `assets_path`    | `Path`                        | Path to assets folder                                |
| `locales_path`   | `Path`                        | Path to locales folder                               |
| `storage_path`   | `Path`                        | Path to storage folder                               |
| `router`         | `Router`                      | The application router instance                      |
| `config`         | `DotDict`                     | Configuration values, accessed as attributes         |
| `catalog`        | `jx.Catalog`                  | Jx component catalog                                 |
| `serializers`    | `tuple[URLSafeTimedSerializer, ...]` | Signed serializers, one per secret key          |
| `signers`        | `tuple[TimestampSigner, ...]`  | Signed signers, one per secret key                   |
| `db`             | `dict[str, pw.Database]`      | Dictionary of Peewee database connections            |
| `queue`          | `Huey`                        | Task queue instance                                  |
| `cache`          | `BaseCache`                   | Cache backend instance                               |
| `mailer`         | `BaseMailer`                  | Email mailer instance                                |
| `i18n`           | `I18n \| None`                | Internationalization instance                        |
| `storage`        | `Storage \| None`             | Storage service instance                             |
| `cable`          | `Cable`                       | WebSocket cable instance for real-time communication |
| `request_cls`    | `type[Request]`               | Request class used for creating request objects      |
| `response_cls`   | `type[Response]`              | Response class used for creating response objects    |

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
| `dumps`            | `(obj, salt=None) -> str`                                  | Serialize and sign a value using the first secret key    |
| `loads`            | `(value, *, max_age=None, return_timestamp=False, salt=None) -> Any` | Deserialize and verify a signed value. Tries all secret keys. Returns `None` if invalid. |
| `on_error`         | `(func) -> func`                                           | Decorator to register error handlers                     |
| `on_teardown`      | `(func) -> func`                                           | Decorator to register teardown handlers                  |


## Request

Accessed via `current.request` or as `self.request` inside a controller. See also: [Controllers — Request and Response](./controllers.md#request-and-response-objects) for quick usage examples.

### Attributes

| Attribute          | Type              | Description                                                    |
|--------------------|-------------------|----------------------------------------------------------------|
| `method`           | `str`             | HTTP method, after HEAD-to-GET and method override processing  |
| `request_method`   | `str`             | Original HTTP method as sent by the client                     |
| `path`             | `str`             | The request path                                               |
| `protocol`         | `str`             | `"http"` or `"https"` (respects `X-Forwarded-Proto`)          |
| `host`             | `str`             | The hostname                                                   |
| `port`             | `int`             | The port number                                                |
| `content_type`     | `str`             | MIME type from the `Content-Type` header                       |
| `content_length`   | `int`             | Body size from the `Content-Length` header                     |
| `headers`          | `MultiDict`       | HTTP request headers                                           |
| `form`             | `MultiDict`       | Parsed request body (form fields and uploaded files)           |
| `matched_route`    | `Route \| None`   | The route matched during routing                               |
| `matched_params`   | `dict \| None`    | Parameters extracted from the URL pattern                      |
| `matched_action`   | `str \| None`     | The action name for the matched route                          |
| `default_format`   | `str`             | Fallback format when accept parsing fails (default: `"html"`)  |

### Properties

| Property           | Type                       | Description                                                         |
|--------------------|----------------------------|---------------------------------------------------------------------|
| `app`              | `App`                      | The application instance                                            |
| `session`          | `DotDict`                  | Session data (read/write)                                           |
| `query`            | `MultiDict`                | Query string parameters                                             |
| `query_string`     | `str`                      | Raw query string                                                    |
| `url`              | `str`                      | Full URL including query string                                     |
| `http_version`     | `str`                      | HTTP version (e.g. `"1.1"`)                                        |
| `flashes`          | `list[tuple[str, str]]`    | Flash messages stored in the session                                |
| `accept`           | `list[str]`                | MIME types from `Accept` header, sorted by quality                  |
| `accept_encoding`  | `list[str]`                | Encodings from `Accept-Encoding`, sorted by quality                 |
| `accept_language`  | `list[str]`                | Languages from `Accept-Language`, sorted by quality                 |
| `cookies`          | `dict[str, str]`           | Parsed cookies                                                      |
| `cookie`           | `dict[str, str]`           | Alias for `cookies`                                                 |
| `date`             | `datetime \| None`         | Parsed `Date` header                                                |
| `default_port`     | `int`                      | Default port for the protocol (443 or 80)                           |
| `format`           | `str`                      | Response format from `Accept` header (e.g. `"html"`, `"json"`)     |
| `forwarded`        | `list[dict[str, str]]`     | Parsed `Forwarded` header                                           |
| `host_with_port`   | `str`                      | `host:port` (omits port if default)                                 |
| `if_none_match`    | `list[str]`                | ETags from `If-None-Match` header                                   |
| `if_modified_since`| `datetime \| None`         | Parsed `If-Modified-Since` header                                   |
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
| `remote_ip`        | `str`                      | Client IP (from `Forwarded`, `X-Forwarded-For`, `X-Real-IP`, or connection) |
| `request_id`       | `str \| None`              | Value of the `X-Request-ID` header                                  |
| `user_agent`       | `str \| None`              | Value of the `User-Agent` header                                    |

### Methods

| Method              | Signature                                                                       | Description                          |
|---------------------|---------------------------------------------------------------------------------|--------------------------------------|
| `get_url`           | `(include_query=True) -> str`                                                   | Build the full URL                   |
| `get_cookie`        | `(name, default=None) -> str \| None`                                           | Get a cookie value by name           |
| `get_signed_cookie` | `(name, default=None, *, salt="", max_age=None) -> str \| Any`                  | Get and verify a signed cookie value |


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

Accessed via `current.response` or as `self.response` inside a controller. See also: [Controllers — Request and Response](./controllers.md#request-and-response-objects) for quick usage examples.

### Attributes

| Attribute          | Type                   | Description                                            |
|--------------------|------------------------|--------------------------------------------------------|
| `status`           | `int`                  | HTTP status code (default: 200)                        |
| `body`             | `str \| bytes \| None` | Response body content                                  |
| `error`            | `Exception \| None`    | Exception that occurred during request processing      |
| `flash`            | `FlashMessages`        | Flash messages manager                                 |
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
| `session`      | `DotDict` | Session data (read/write)             |
| `has_body`     | `bool`    | `True` if the response has a body     |
| `status_code`  | `int`     | Alias for `status`                    |

### Header Properties

All of these are read/write.

| Property           | Type                | Description                         |
|--------------------|---------------------|-------------------------------------|
| `accept_ranges`    | `str \| None`       | `Accept-Ranges` header              |
| `cache_control`    | `list[str] \| None` | `Cache-Control` directives          |
| `content_encoding` | `str \| None`       | `Content-Encoding` header           |
| `content_length`   | `int \| None`       | `Content-Length` header              |
| `content_location` | `str \| None`       | `Content-Location` header           |
| `content_range`    | `str \| None`       | `Content-Range` header              |
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
| `redirect_to`        | `(url_or_route, obj=None, *, flash=None, flash_type="info", status=303, **kw) -> None`                    | Redirect to a URL or named route with optional flash     |
| `fresh_when`         | `(objects=None, *, etag=None, last_modified=None, strong=False, public=False, request=None) -> bool`       | Set cache headers and return whether the response is fresh |
| `is_fresh`           | `(request=None) -> bool`                                                                                   | Check if response is fresh based on request cache headers |
| `send_file`          | `(path, *, mimetype=None, as_attachment=False, download_name=None, x_sendfile_header="") -> None`          | Send a file as the response body                         |
| `set_cookie`         | `(name, value="", *, max_age=None, path="/", domain=None, secure=False, httponly=False, samesite="Lax", comment="", signed=False, salt="") -> None` | Set a response cookie |
| `unset_cookie`       | `(name) -> None`                                                                                           | Delete a cookie                                          |
| `set_signed_cookie`  | `(name, value="", *, max_age=None, path="/", domain=None, secure=False, httponly=False, samesite="Lax", comment="", salt="") -> None` | Set a cryptographically signed cookie |
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

Cookies default to `samesite="Lax"`. Signed cookies use the app's secret key.

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

Everything below is importable from `proper` (e.g., `from proper import Concern`).

### Concern

Base class for controller concerns (mixins with callbacks). See [Controllers — Concerns](controllers.md#concerns).

```python
from proper import Concern

class TeamScoped(Concern):
    before = {"do": "set_team"}

    def set_team(self):
        ...
```

### Routing

See [Routing](routing.md) for full details.

| Symbol         | Description                                                    |
|----------------|----------------------------------------------------------------|
| `Router`       | Main router — registers routes via `resources()`, `route()`, etc. |
| `ScopedRouter` | Nested router returned by `scope()` and `namespace()` blocks   |
| `Route`        | A single registered route (name, path, method, controller, action) |
| `StaticRoute`  | Route for serving static assets                                |

### Models

See [Models](models.md) for full details.

| Symbol        | Description                                                           |
|---------------|-----------------------------------------------------------------------|
| `ProperModel` | Base Peewee model with scope support and token generation methods     |
| `scope`       | Decorator that tags a classmethod as a chainable query scope          |

### Channel

WebSocket channel base class. See [Channels](channels.md) for full details.

| Method             | Description                                      |
|--------------------|--------------------------------------------------|
| `subscribed()`     | Called when a client subscribes — override to set up streams |
| `unsubscribed()`   | Called on disconnect — override for cleanup       |
| `stream_from(name)`| Subscribe this connection to a broadcast stream   |
| `stop_stream_from(name)` | Unsubscribe from a stream                  |
| `stop_all_streams()` | Unsubscribe from all streams                    |
| `send(data)`       | Send data to this connection                     |
| `broadcast(stream, data)` | Broadcast data to all subscribers of a stream |
| `reject()`         | Reject the subscription                         |

### Emails

See [Emails](emails.md) for full details.

| Symbol             | Description                                              |
|--------------------|----------------------------------------------------------|
| `EmailMessage`     | Compose an email (subject, to, body, attachments)        |
| `BaseMailer`       | Abstract mailer backend                                  |
| `SMTPMailer`       | Send via SMTP                                            |
| `ToConsoleMailer`  | Print emails to stdout (development)                     |
| `ToMemoryMailer`   | Store emails in a list (testing)                         |
| `EmailAttachment`  | TypedDict for file attachments                           |
| `EmailAlternative` | TypedDict for alternative content parts                  |

### Helpers

Utility functions and classes available from `proper`.

| Symbol            | Description                                                    |
|-------------------|----------------------------------------------------------------|
| `DotDict`         | Dict subclass with attribute-style access (`d.key`)            |
| `MultiDict`       | Dict that supports multiple values per key (query/form params) |
| `JSONField`       | Peewee field that stores JSON with transparent serialization   |
| `Undefined`       | Sentinel value for distinguishing "not provided" from `None`   |
| `import_string`   | Import a dotted module path and return the attribute            |
| `make_list`       | Wrap a value in a list if it isn't one already                 |
| `secure_filename` | Sanitize a filename for safe filesystem storage                |

### Global Context

See [Application — Global Context](app.md#global-context).

```python
from proper import current

current.app       # App instance
current.request   # Current Request
current.response  # Current Response
current.user      # Current user (set by auth, defaults to None)
current.locale    # Current locale (set by i18n, defaults to None)
current.timezone  # Current timezone (set by i18n, defaults to None)
```

`current` uses Python `ContextVar` under the hood, so it's safe for concurrent requests.

### Units

Time and size constants from `proper.units`, used in rate limiting, caching, and cookie configuration.

```python
from proper.units import MINUTES, HOURS, DAYS, MB
```

**Time** (all values in seconds): `SECOND`/`SECONDS`, `MINUTE`/`MINUTES`, `HOUR`/`HOURS`, `DAY`/`DAYS`, `WEEK`/`WEEKS`, `MONTH`/`MONTHS`, `YEAR`/`YEARS`.

**Size** (all values in bytes): `B`, `KB`, `MB`, `GB`, `TB`.

**Function**: `to_seconds(**kwargs)` — converts `timedelta` keyword arguments to an integer seconds value.

