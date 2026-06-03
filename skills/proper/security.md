---
title: Security
description: CSRF protection, rate limiting, sessions, signed cookies, security headers
last_verified: 2026-04-02
---

# Security

Proper includes several built-in security mechanisms: origin-based CSRF protection, rate limiting, signed sessions, security response headers, and request size limits. Most of these are enabled by default through the generated `AppController`.

For user authentication (registration, login, password reset), see [Authentication](auth.md).

## Table of Contents

- [Origin Protection (CSRF)](#origin-protection-csrf)
- [Rate Limiting](#rate-limiting)
- [Sessions](#sessions)
- [Secret Keys](#secret-keys)
- [Signed Cookies](#signed-cookies)
- [Security Headers](#security-headers)
- [Request Size Limits](#request-size-limits)


## Origin Protection (CSRF)

The `OriginProtection` concern prevents Cross-Site Request Forgery attacks by verifying that state-changing requests come from trusted origins. It's included in `AppController` by default and works automatically for same-origin apps.

To allow cross-origin requests from specific domains, add them to `TRUSTED_ORIGINS` in your config:

```python
TRUSTED_ORIGINS = [
    "https://app.example.com",
    "https://api.example.com:8443",
]
```

Requests where both the `Origin` and the `Host` are on the local network (private IPs, loopback, or link-local addresses) are always allowed. This enables development across LAN devices — for example, testing from a phone at `http://192.168.1.50:2300` against a dev server on `192.168.1.100`.

For the full verification algorithm, configuration details, and the legacy `RequestForgeryProtection` alternative, see [Controllers — Concerns](controllers.md#concerns).


## Rate Limiting

The `RateLimiting` concern limits requests per identity within a time window. It's included in `AppController` by default but only activates when a controller defines a `rate_limit` attribute. Requires a configured cache store (`app.cache`).

```python
from proper.units import MINUTES

class SessionController(AppController):
    rate_limit = {"to": 10, "within": 3 * MINUTES, "only": "create"}
```

For the full options table, multiple limits, custom identity/scope, custom reactions, and resetting limits, see [Controllers — Concerns](controllers.md#concerns).


## Sessions

Sessions are stored in a signed cookie named `_session`. The cookie value is a JSON dictionary signed with HMAC-SHA256 using the app's secret keys.

### How It Works

1. On each request, the `_session` cookie is read and verified.
2. The deserialized data is available as `request.session` (a `DotDict` with dot-notation access).
3. A copy is placed in `response.session` for the controller to modify.
4. After the response, if `response.session` differs from `request.session`, a new signed cookie is written.
5. If `response.session` is empty, the cookie is cleared.

### Using Sessions

In controllers, read from `self.request.session` and write to `self.response.session`:

```python
def create(self):
    self.response.session["user_id"] = user.id
    self.response.session["return_to"] = "/dashboard"

def show(self):
    user_id = self.request.session.get("user_id")
    return_to = self.request.session.return_to  # dot notation works too
```

### Flash Messages

Flash messages are one-time notifications stored in the session. They're automatically cleared after being read:

```python
# Set a flash (usually via redirect_to)
self.response.redirect_to("Photo.index", flash="Photo was deleted")

# In templates, flash messages are available as a list of (type, message) tuples
```

Flash messages are stored under a reserved key in the session. On the next request, they appear in `request.session` and are automatically removed from `response.session`.

### Configuration

Session cookie settings in `config/main.py`:

```python
SESSION_COOKIE_LIFETIME = 30 * DAYS    # Max age in seconds (default: 30 days)
SESSION_COOKIE_DOMAIN = None           # Restrict to domain (default: None)
SESSION_COOKIE_PATH = "/"              # Cookie path (default: "/")
SESSION_COOKIE_HTTPONLY = True          # Block JavaScript access (default: True)
SESSION_COOKIE_SAMESITE = "Lax"        # "Lax", "Strict", or "None" (default: "Lax")
```

The `secure` flag is set automatically when the request arrives over HTTPS.


## Secret Keys

Secret keys are used to sign sessions, cookies, and tokens. They're configured as a list in `config/main.py`, ordered **oldest to newest**:

```python
SECRET_KEYS = [
    "old-key-at-least-48-characters-long-for-proper-security-abcdef",
    "new-key-at-least-48-characters-long-for-proper-security-123456",
]
```

### Requirements

- At least one key must be provided (the app won't start without it)
- Each key must be at least 48 characters long
- Keys should be cryptographically random

### Key Rotation

All keys in the list are valid for verification, but only the **last key** (newest) is used for signing. This lets you rotate keys without invalidating existing sessions:

1. Generate a new key and append it to the list
2. Deploy — new signatures use the new key, old signatures still verify
3. After enough time has passed (e.g., `SESSION_COOKIE_LIFETIME`), remove the oldest key

### Signing and Serialization

The app provides `dumps()` and `loads()` for cryptographic signing and serialization:

```python
# Sign and serialize any JSON-serializable value
token = app.dumps({"user_id": 42}, salt="my-feature")

# Verify and deserialize (returns None if invalid or expired)
data = app.loads(token, max_age=3600, salt="my-feature")
```

These use [itsdangerous](https://itsdangerous.palletsprojects.com/) `URLSafeTimedSerializer` with HMAC key derivation, producing URL-safe tokens that include a timestamp. Only the newest secret key is used for signing; all keys are tried for verification.

For model-level token workflows (password resets, email verification, signed URLs), use the `generate_token()` / `resolve_token()` API on `ProperModel` instead of calling `app.dumps()` / `app.loads()` directly. See [Token Generation](models.md#token-generation).


## Signed Cookies

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

### Cookie Prefixes

Proper recognizes two standard cookie prefixes that enforce security constraints:

- `__Host-` — forces `path=/`, `secure=True`, and no `domain`
- `__Secure-` — forces `secure=True`

```python
self.response.set_cookie("__Host-session", value, secure=True)
```

### Cookie Options

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

### Disabling Cookies

For read-only endpoints (RSS feeds, public API responses), you can disable all cookie writes:

```python
class FeedController(AppController):
    def index(self):
        self.response.disable_cookies = True
        # No cookies will be sent, including session updates
```


## Security Headers

The generated `SecurityHeaders` concern sets protective response headers on every request:

```python
from proper import Concern


class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        self.response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        self.response.headers.setdefault("X-XSS-Protection", "1; mode=block")
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


## Request Size Limits

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

### Multipart Form Limits

Multipart form uploads have additional per-field limits:

```python
# config/main.py
from proper.units import MB

MAX_FORM_FILES = 10          # Max number of file fields (default: 10)
MAX_FORM_FIELDS = 100        # Max number of non-file fields (default: 100)
MAX_FORM_PART_SIZE = 2 * MB  # Max size per individual part (default: 2 MB)
```

These protect against abuse from forms with excessive fields or oversized individual parts.


## Gotchas

- `SECRET_KEYS` list is ordered oldest → newest; only the last key signs, all keys verify
- Signed cookies must use the same `salt` on both `set_signed_cookie()` and `get_signed_cookie()`
