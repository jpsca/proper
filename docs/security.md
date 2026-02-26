title: Security
----

# Security

Proper includes several built-in security mechanisms: origin-based CSRF protection, rate limiting, signed sessions, security response headers, and request size limits. Most of these are enabled by default through the generated `AppController`.


## 1. Origin Protection (CSRF)

The `OriginProtection` concern prevents Cross-Site Request Forgery attacks by verifying that state-changing requests come from trusted origins. It's included in `AppController` by default.

### 1.1 How It Works

On every request, the concern runs a `before` callback with this algorithm:

1. **Safe methods** — GET, HEAD, OPTIONS, and QUERY requests are always allowed (they should not change state).
2. **Non-browser requests** — If neither `Sec-Fetch-Site` nor `Origin` headers are present, the request is allowed. Non-browser clients (APIs, cURL) can't be used for CSRF.
3. **Trusted origins** — If the `Origin` header matches a value in `TRUSTED_ORIGINS`, the request is allowed.
4. **Modern browsers** — If `Sec-Fetch-Site` is `"same-origin"` or `"none"`, the request is allowed.
5. **Legacy browsers** — If `Origin` host:port matches the `Host` header, the request is allowed.
6. **Reject** — Otherwise, raises `InvalidOrigin` (403 Forbidden).

### 1.2 Trusted Origins

To allow cross-origin requests from specific domains (e.g., a separate frontend), add them to `TRUSTED_ORIGINS` in your config. Include the protocol and port:

```python
TRUSTED_ORIGINS = [
    "https://app.example.com",
    "https://api.example.com:8443",
]
```

### 1.3 Usage

`OriginProtection` is already included in the generated `AppController`:

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

No configuration is needed for same-origin apps. The concern works automatically.


## 2. Rate Limiting

The `RateLimiting` concern limits the number of requests per identity within a time window. It's included in `AppController` by default but only activates when a controller defines a `rate_limit` attribute.

Rate limiting requires a configured cache store (`app.cache`).

### 2.1 Basic Usage

```python
from proper.units import MINUTES

class SessionController(AppController):
    rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}
```

This allows 10 POST requests to the `create` action per 3 minutes, per IP address.

### 2.2 Options

| Option       | Type                  | Default               | Description                              |
|--------------|-----------------------|-----------------------|------------------------------------------|
| `to`         | int, str, or callable | (required)            | Max requests in the window               |
| `within`     | int, str, or callable | (required)            | Time window in seconds                   |
| `by`         | str or callable       | `request.remote_ip`   | Identity for the limit                   |
| `scope`      | str                   | controller module path | Namespace for the cache key              |
| `name`       | str                   | `""`                  | Distinguishes multiple limits per scope  |
| `only`       | str or list           | all actions            | Actions this limit applies to            |
| `exclude`    | str or list           | none                   | Actions exempt from this limit           |
| `react_with` | str or callable       | raise `TooManyRequests` | Custom handler when limit is exceeded   |

When `to` or `within` is a string, it's treated as a method name on the controller and called at request time.

### 2.3 Multiple Limits

Pass a list to define multiple rate limits on one controller. Use `name` to distinguish them:

```python
from proper.units import SECONDS, MINUTES

class SessionController(AppController):
    rate_limit = [
        {"to": 3, "within": 2 * SECONDS, "name": "short-term"},
        {"to": 10, "within": 5 * MINUTES, "name": "long-term"},
    ]
```

### 2.4 Custom Identity and Scope

```python
from proper import current
from proper.units import MINUTE, HOUR

class APIController(AppController):
    rate_limit = [
        {"to": 10, "within": 3 * MINUTE},
        {"to": "max_requests", "within": "time_window",
         "by": lambda self: current.user.id},
    ]

    def max_requests(self):
        return 1000 if current.user.premium else 100

    def time_window(self):
        return 1 * HOUR if current.user.premium else 1 * MINUTE
```

### 2.5 Custom Reaction

Instead of raising `TooManyRequests`, redirect the user or do something else:

```python
class SignupsController(AppController):
    rate_limit = {
        "to": 1000,
        "within": 10 * SECONDS,
        "by": lambda self: self.request.host,
        "react_with": "redirect_to_busy",
        "only": "new",
    }

    def redirect_to_busy(self):
        self.response.redirect_to("Busy.show", flash="Too many signups!")
```

### 2.6 Resetting a Limit

Reset a rate limit counter manually (e.g., after a successful login):

```python
self.reset_rate_limit(by=user.login, scope="sessions", name="login")
```

The cache key format is `rate-limit:{scope}:{name}:{identity}`.


## 3. Sessions

Sessions are stored in a signed cookie named `_session`. The cookie value is a JSON dictionary signed with HMAC-SHA256 using the app's secret keys.

### 3.1 How It Works

1. On each request, the `_session` cookie is read and verified.
2. The deserialized data is available as `request.session` (a `DotDict` with dot-notation access).
3. A copy is placed in `response.session` for the controller to modify.
4. After the response, if `response.session` differs from `request.session`, a new signed cookie is written.
5. If `response.session` is empty, the cookie is cleared.

### 3.2 Using Sessions

In controllers, read from `self.request.session` and write to `self.response.session`:

```python
def create(self):
    self.response.session["user_id"] = user.id
    self.response.session["return_to"] = "/dashboard"

def show(self):
    user_id = self.request.session.get("user_id")
    return_to = self.request.session.return_to  # dot notation works too
```

### 3.3 Flash Messages

Flash messages are one-time notifications stored in the session. They're automatically cleared after being read:

```python
# Set a flash (usually via redirect_to)
self.response.redirect_to("Photo.index", flash="Photo was deleted")

# In templates, flash messages are available as a list of (type, message) tuples
```

Flash messages are stored under a reserved key in the session. On the next request, they appear in `request.session` and are automatically removed from `response.session`.

### 3.4 Configuration

Session cookie settings in `config/main.py`:

```python
SESSION_COOKIE_LIFETIME = 30 * DAYS    # Max age in seconds (default: 30 days)
SESSION_COOKIE_DOMAIN = None           # Restrict to domain (default: None)
SESSION_COOKIE_PATH = "/"              # Cookie path (default: "/")
SESSION_COOKIE_HTTPONLY = True          # Block JavaScript access (default: True)
SESSION_COOKIE_SAMESITE = "Lax"        # "Lax", "Strict", or "None" (default: "Lax")
```

The `secure` flag is set automatically when the request arrives over HTTPS.


## 4. Secret Keys

Secret keys are used to sign sessions, cookies, and tokens. They're configured as a list in `config/main.py`, ordered **oldest to newest**:

```python
SECRET_KEYS = [
    "old-key-at-least-48-characters-long-for-proper-security-abcdef",
    "new-key-at-least-48-characters-long-for-proper-security-123456",
]
```

### 4.1 Requirements

- At least one key must be provided (the app won't start without it)
- Each key must be at least 48 characters long
- Keys should be cryptographically random

### 4.2 Key Rotation

All keys in the list are valid for verification, but only the **last key** (newest) is used for signing. This lets you rotate keys without invalidating existing sessions:

1. Generate a new key and append it to the list
2. Deploy — new signatures use the new key, old signatures still verify
3. After enough time has passed (e.g., `SESSION_COOKIE_LIFETIME`), remove the oldest key

### 4.3 Signing and Serialization

The app provides two methods for cryptographic signing:

```python
# Signer — signs raw values with HMAC-SHA1
signer = app.get_signer(namespace="my-feature")
signed = signer.sign("value")
original = signer.unsign(signed)

# Serializer — signs and serializes JSON with HMAC-SHA256
serializer = app.get_serializer(namespace="my-feature")
token = serializer.dumps({"user_id": 42})
data = serializer.loads(token, max_age=3600)  # raises if older than 1 hour
```

Both use [itsdangerous](https://itsdangerous.palletsprojects.com/) with HMAC key derivation. The serializer uses `URLSafeTimedSerializer`, producing URL-safe tokens that include a timestamp.


## 5. Signed Cookies

Any cookie can be cryptographically signed to prevent tampering:

```python
# Set a signed cookie
self.response.set_signed_cookie(
    "preferences",
    {"theme": "dark", "lang": "en"},
    salt="prefs",
    max_age=30 * DAYS,
    httponly=True,
    samesite="Lax",
)

# Read it back (returns None if tampered or expired)
prefs = self.request.get_signed_cookie("preferences", salt="prefs", max_age=30 * DAYS)
```

The `salt` parameter adds an extra layer of key derivation. You must use the same salt for both setting and reading.

### 5.1 Cookie Prefixes

Proper recognizes two standard cookie prefixes that enforce security constraints:

- `__Host-` — forces `path=/`, `secure=True`, and no `domain`
- `__Secure-` — forces `secure=True`

```python
self.response.set_cookie("__Host-session", value, secure=True)
```

### 5.2 Cookie Options

All `set_cookie` / `set_signed_cookie` options:

| Option     | Default  | Description                                        |
|------------|----------|----------------------------------------------------|
| `max_age`  | `None`   | Lifetime in seconds (also sets `Expires`)          |
| `path`     | `"/"`    | Cookie path                                        |
| `domain`   | `None`   | Cookie domain                                      |
| `secure`   | `False`  | Only send over HTTPS                               |
| `httponly`  | `False`  | Block JavaScript access                            |
| `samesite` | `"Lax"`  | `"Lax"`, `"Strict"`, or `None`                     |
| `salt`     | `""`     | Extra key derivation salt (signed cookies only)    |

Cookies larger than 4093 bytes trigger a warning, as some browsers silently ignore oversized cookies.

### 5.3 Disabling Cookies

For read-only endpoints (RSS feeds, public API responses), you can disable all cookie writes:

```python
class FeedController(AppController):
    def index(self):
        self.response.disable_cookies = True
        # No cookies will be sent, including session updates
```


## 6. Security Headers

The generated `SecurityHeaders` concern sets protective response headers on every request:

```python
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

| Header                              | Value                              | Purpose                                          |
|-------------------------------------|------------------------------------|--------------------------------------------------|
| `X-Frame-Options`                   | `SAMEORIGIN`                       | Prevent clickjacking via iframes                 |
| `X-XSS-Protection`                  | `1; mode=block`                    | Block reflected XSS (legacy browsers)            |
| `X-Download-Options`                | `noopen`                           | Force download instead of opening in browser     |
| `X-Permitted-Cross-Domain-Policies` | `none`                             | Disable Flash/PDF cross-domain policies          |
| `Referrer-Policy`                   | `strict-origin-when-cross-origin`  | Limit referrer info sent to other origins        |

This concern lives in your app at `controllers/concerns/security_headers.py`. You can customize it by changing the defaults or adding headers like `Content-Security-Policy`.

Using `setdefault` means individual controllers can override any header before the `after` callback runs.


## 7. Request Size Limits

Proper enforces size limits on incoming requests to prevent denial-of-service attacks and memory exhaustion:

```python
# config/main.py
from proper.units import MB

MAX_CONTENT_LENGTH = 8 * MB    # Request body limit (default: 8 MB)
MAX_QUERY_SIZE = 1 * MB        # Query string limit (default: 1 MB)
```

- Exceeding `MAX_CONTENT_LENGTH` raises `RequestEntityTooLarge` (413)
- Exceeding `MAX_QUERY_SIZE` raises `UriTooLong` (414)

These limits are enforced before parsing, so oversized payloads don't consume memory.
