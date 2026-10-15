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
- [Trusted Proxies](#trusted-proxies)


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

1. On each request, the `_session` cookie is read and verified. A missing cookie, a bad or expired signature, or a value that is not a JSON object gives an empty session.
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

The `secure` flag is set automatically when the request arrives over HTTPS (`request.is_secure`: the scheme, or `X-Forwarded-Proto` when the peer is in `TRUSTED_PROXIES`).


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

# Verify and deserialize (returns None if invalid, expired or undecodable)
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

The `salt` parameter adds an extra layer of key derivation. You must use the same salt for both setting and reading. Both methods default to `"cookie"`, so a cookie set without a salt reads back without one.

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
| `salt`     | `"cookie"` | Extra key derivation salt (signed cookies only)  |

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

These limits are enforced before parsing, so oversized payloads don't consume memory. A body with a `Content-Length` over the limit is refused before a byte is read; a body without one (chunked, or HTTP/2 without the header) is read until it passes the limit, then refused.

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


## Trusted Proxies

`X-Forwarded-For`, `Forwarded`, `X-Real-IP` and `X-Forwarded-Proto` are used (for `request.remote_ip` and `request.protocol`, so `is_secure`, `host_with_port` and the session and auth cookies' `Secure` flag) only when the peer is in `TRUSTED_PROXIES`, or has no address (`proper run` or gunicorn on a Unix socket); from any other address they are ignored and `remote_ip` is the peer's address.

```python
# config/main.py. Default: the loopback, private and link-local networks
# (127.0.0.0/8, ::1, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16,
#  169.254.0.0/16, fc00::/7, fe80::/10). The list replaces the default.
TRUSTED_PROXIES = ["127.0.0.1", "203.0.113.0/24"]
TRUSTED_PROXIES = []  # app faces the internet directly: ignore the headers
```

- Each item is an IP or a CIDR network, as a string or an `ipaddress` object; anything else (an int, bytes, a hostname) is a `ConfigError` at startup.
- The default trusts every loopback, private and link-local address. A client that reaches the app, or the first proxy, from such an address (the same LAN or VPC, a container on the same host, a load balancer that rewrites the source address) is taken for a proxy: it can set `remote_ip` (`X-Forwarded-For`, `X-Real-IP`) and make the request secure (`X-Forwarded-Proto: https`). If clients can connect from those networks, list only your proxies' addresses.
- The trusted proxy must overwrite `X-Forwarded-Proto` with the scheme it got the request on (nginx: `proxy_set_header X-Forwarded-Proto $scheme;`), not append to it or pass the client's through: the app uses the header's whole value.
- `remote_ip`: `X-Forwarded-For`, else `Forwarded`, else `X-Real-IP`. The first two are read from the right, skipping trusted proxies; if all are trusted, the leftmost. A value that is not an IP (`unknown`, `_hidden`) stops the walk and is returned. An `X-Forwarded-For` or `Forwarded` address is returned without its port and brackets (`"[2001:db8::1]:4711"` gives `2001:db8::1`), and `::ffff:1.2.3.4` as `1.2.3.4`. `Forwarded` is split into elements at the commas outside quoted strings, from the right, so a comma in a quoted value of the proxy's element (`host="a,b"`) doesn't split it, and a quote the client leaves open can't take in the proxy's element. A header sent in several lines is read as one list, the lines in order.
- List every proxy in the chain, including a CDN or public load balancer in front of a local nginx: otherwise `remote_ip` is the CDN edge's address for every visitor, and the default `rate_limit` puts them all in one bucket.
- A proxy passes the client's forwarding headers through. One that writes only `Forwarded` must remove the client's `X-Forwarded-For`; one that writes only `X-Real-IP` must remove `X-Forwarded-For` and `Forwarded`.
- The proxy must drop request headers with `_` in the name (`X_Forwarded_For`, `X_Forwarded_Proto`): WSGI gives them to the app under the same name as the `-` ones, `proper run` drops them, but other WSGI servers can keep the client's value. nginx drops them unless `underscores_in_headers` is on or `ignore_invalid_headers` is off; Go's `httputil.ReverseProxy` passes them.
- waitress and uWSGI on a Unix socket give a made-up peer address (`localhost`, `0.0.0.0`), which is not trusted.
- `TestClient` requests come from `client.remote_ip` (`127.0.0.1`, trusted), so test headers like `X-Forwarded-For` are honored; set a public `client.remote_ip` and they are ignored. `make_test_request()` without `client=` has no peer address, which counts as trusted. A WebSocket handshake without a peer address (the in-memory server's `connect()` without details) doesn't count: its `X-Forwarded-For` is dropped.

## Host header

- `request.host` and `request.port` come from the `Host` header (PEP 3333), else from the address the server listens on (`SERVER_NAME`, `0.0.0.0` under `proper run`). Host-constrained routes and `OriginProtection` compare with it. The proxy must pass the client's `Host` (nginx: `proxy_set_header Host $host;`; its default sends the upstream's address).
- An invalid `Host` (`example.com/x`, a space, `user@host`) is a 400, and so is a request with more than one `Host` line (RFC 9112 §3.2): the server joins them with a comma, so a `Host` with a comma is refused.
- The client chooses the `Host` header. Proper uses it only to pick the route and to compare with `Origin`; it never builds a URL from it: `url_for(..., _full=True)`, the password-reset email and the storage URLs use `PROTOCOL` and `HOST` from the config (or the route's own host). Do the same in your code: build absolute URLs that leave the request (emails, links stored or sent to others) with `url_for(_full=True)`, not from `request.host`.
- `X-Forwarded-Host` and `Forwarded: host=` are not read.

## Gotchas

- `SECRET_KEYS` list is ordered oldest → newest; only the last key signs, all keys verify
- Signed cookies must use the same `salt` on both `set_signed_cookie()` and `get_signed_cookie()`
