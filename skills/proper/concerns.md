---
title: Callbacks and Concerns
description: before/after callbacks, writing a concern, and the built-in concerns: OriginProtection, Pagination, RateLimiting, CurrentLocale, CurrentTimezone, SecurityHeaders
last_verified: 2026-11-01
sources:
  - src/proper/concerns
  - src/proper/controller
---

# Callbacks and Concerns

Cross-cutting controller behavior: callbacks that run around every action, and concerns (mixins) that package callbacks and helpers. Controllers themselves are in [controllers.md](controllers.md).

## Table of Contents

- [Controller Callbacks](#controller-callbacks)
- [Concerns](#concerns)


## Controller Callbacks

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
- **If a before callback sets `response.body` (directly, via a redirect, or by returning a value), the action is never called**, and neither are the `after` callbacks
- Before callbacks run outer-first: parent class → child class. After callbacks run inner-first: child class → parent class. Concerns mixed into a parent count as "outer" relative to the child controller.

### `before` callback

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

The `"do"` argument is one method name, defined in the class or in one of its parent classes. To run several, use a list of dicts, or name a property that returns a list of callables. A `do` that names a missing attribute fails at startup (`LoweringError`).

`before` callbacks are for cross-cutting checks that halt the request: authentication, authorization, CSRF, locale. Do **not** use them to load records or build forms. Load the record and the form inside each action (with a private `load_card()` helper that sets `self.card` to the record or `None`, and `raise NotFound` in the action), so each action shows everything it needs.

The `only` option runs the callback only for the listed actions; there is also an `exclude` option which works the other way.

**Warning:** If a before callback sets `response.body`, the action is never called — this is logged.

### `after` callback

You can also define action callbacks to run after a controller action has been executed with the `after` callback.

The `after` callbacks are similar to the `before` callbacks, but because the controller action has already been run they have access to the response data that's about to be sent to the client. A common use case is setting response headers:

```python
class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-Content-Type-Options", "nosniff")
        self.response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

**Warning:** `after` callbacks are executed only after a successful controller action, and not if an exception is raised in the request cycle.


### Multiple callbacks

Both `before` and `after` callbacks can be written as list of dictionaries, to have many callbacks with different options in the same controller. The callbacks will be executed in MRO order.

```python
from .app_controller import AppController

class CardController(AppController):
    before = [
        {"do": "require_login", "exclude": ("index", "show")},
        {"do": "ensure_editor_access", "only": ["edit", "update", "delete"]},
    ]

    ...
```

### Inheritance

The `before` and `after` callbacks are always inherited and are not obscured by new declarations. Invoking an action in a controller with `before` callbacks defined, will first call any `before` callbacks defined in its parent classes, and then the ones defined in the controller class itself.

For example, if `AppController` has a `before` callback that checks authentication, and `CardController` has a `before` callback that checks authorization, both will run — the authentication check first (from the parent), then the authorization check (from the child).


## Concerns

A controller concern is a mixin class that defines callbacks and methods that can be shared across multiple controllers. Concern classes inherit from `proper.Concern` and follow the same `before`/`after` callback pattern as controllers.

The convention is to declare them in the `myapp/controllers/concerns/` directory, one per file.

### Writing a Concern

```python {title="myapp/controllers/concerns/team_scoped.py"}
from proper import Concern
from ...models import Team


class TeamScoped(Concern):
    def load_team(self):
        team_id = self.params.get("team_id", "")
        self.team = Team.find(int(team_id)) if team_id.isdigit() else None
```

Then mix it into any controller that needs it:

```python
class ProjectController(TeamScoped, AppController):
    def index(self):
        self.load_team()
        if not self.team:
            raise NotFound
        self.projects = self.team.projects
```

### Built-in Concerns

These concerns are available from `proper.concerns`:

#### OriginProtection

Verifies that state-changing requests (POST, PATCH, PUT, DELETE) come from the same origin or a trusted origin. This is the modern CSRF protection approach that doesn't require tokens.

The verification algorithm:

1. Allow all GET, HEAD, OPTIONS, and QUERY requests (safe methods).
2. If neither `Sec-Fetch-Site` nor `Origin` headers are present, allow the request (not a browser request).
3. If the `Origin` header matches the `TRUSTED_ORIGINS` config, allow the request.
4. If `Sec-Fetch-Site` is `same-origin` or `none`, allow the request (modern browsers).
5. If the `Origin`'s host and port match the `Host` header, allow the request (HTTP or old browsers).
6. If both the `Origin` and the `Host` are on the local network (`localhost`, or a private, loopback or link-local IP address), allow the request.
7. Otherwise, raise `InvalidOrigin` (403 Forbidden).

An `Origin` that is not a valid URL (`http://[abc]`) matches no host in steps 5 and 6.

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


#### Pagination

Paginates a Peewee query with **geared page sizes** (a port of Basecamp's geared_pagination). Included in the default `AppController`.

Call `paginate_for` from an action; it reads the `page` param (`self.params`, so a route or form value works too), sets `self.page`, and returns the current page's records:

```python
def index(self):
    self.posts = self.paginate_for(
        Post.select().order_by(Post.created_at.desc()),
        per_page=[15, 30, 50, 100],  # geared: page 1->15, 2->30, 3->50, 4+->100
    )
```

`paginate_for(query, *, per_page=None, ordered_by=None, cursor_secret=None)`:

- `per_page`: an int (fixed size) or a list of ints (geared sizes; the last repeats). Defaults to `[15, 30, 50, 100]`.
- `ordered_by`: pass it to switch from `LIMIT/OFFSET` to **cursor (keyset)** paging. A list of `(field, "asc"|"desc")` pairs, bare fields (ascending), or a dict. The last column must be unique (usually the primary key). Cursor paging is count-free.
- `cursor_secret`: optional secret to sign cursor tokens (tamper-detected on decode).

`self.page` is a `Page`: `.records`, `.number`, `.size`, `.is_first`, `.is_last`, `.is_only`, `.is_before_last`, `.is_empty`, `.next_param` (next page number, cursor token, or `None` on the last page), `.cache_key`, plus `.recordset.page_count` and `.recordset.records_count`. The `Page` is iterable and `len()`-able.

On JSON responses the concern sets `X-Total-Count` (offset mode only) and a `Link: rel="next"` header (omitted on the last page), and folds `self.page.cache_key` into the response `etag`.


#### RateLimiting

Limits the number of requests per time window. By default, rate limits apply per IP address (`request.remote_ip`; behind a CDN or load balancer, list every proxy in the chain in `TRUSTED_PROXIES` or all visitors share the proxy's limit), but you can customize the identity, scope, and reaction.

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

A `to`, `within`, `by` or `react_with` given as a string names a method, which is called (a property won't work; the lambda form does). After `react_with` runs without setting a body, the action still runs. A `by` identity taken from the request (a form value, a header, `request.host`) is chosen by the client: changing it gives a new limit. Use one only for what the limit protects (the login of an account) and keep a limit by IP next to it. Never key on `request.host`: it is the client's `Host` header, which every route without a `host` accepts.

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
            flash_cat="negative",
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

#### CurrentLocale

Resolves the current locale for the request and assigns it to `current.locale` in a `before` callback. Wired up by the `i18n` addon — see [i18n.md](i18n.md).

Resolution order: URL param → cookie → `current.user.locale` → `app.i18n.negotiate_locale(accept_language)` → `LOCALE_DEFAULT` config.

The concern also extends `etag` to include `current.locale`, so cached responses vary by language.

#### CurrentTimezone

Resolves the current timezone and assigns it to `current.timezone` in a `before` callback. Wired up by the `i18n` addon — see [i18n.md](i18n.md).

Resolution order: URL param → cookie → `current.user.timezone` → `TIMEZONE_DEFAULT` config.

Like `CurrentLocale`, this concern extends `etag` to include `current.timezone`.

#### SecurityHeaders

Sets security-related response headers as an `after` callback. This concern is defined in your app (not in the framework) so you can customize it:

```python {title="myapp/controllers/concerns/security_headers.py"}
from proper import Concern


class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        headers = self.response.headers
        headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-XSS-Protection", "0")
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
```

There is no `Content-Security-Policy` by default; see [security.md](security.md#security-headers). The generated file ends with a commented-out `Strict-Transport-Security` header to turn on once the site is HTTPS-only.
