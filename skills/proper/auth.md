---
title: Authentication
description: Auth addon — user registration, login/logout, password reset, session management
last_verified: 2026-06-05
---

# Authentication

Proper Auth is an installable addon that provides a complete user/password authentication system as an installable blueprint. It includes user registration, login/logout, password hashing with automatic hash upgrades, session management, password reset via email, rate limiting, and "Have I Been Pwned?" password checking.

For sessions, CSRF protection, rate limiting, and other security mechanisms, see [Security](security.md).

## Table of Contents

- [Setup](#setup)
- [Configuration](#configuration)
- [The User Model](#the-user-model)
- [The Session Model](#the-session-model)
- [The Authentication Concern](#the-authentication-concern)
- [Sign-Up](#sign-up)
- [Login and Logout](#login-and-logout)
- [Password Reset](#password-reset)
- [Forms](#forms)
- [CLI Commands](#cli-commands)
- [Security Features](#security-features)
- [Full Authentication Flow](#full-authentication-flow)


## Setup

Install the auth blueprint with:

```bash
proper install auth
proper db migrate
```

This generates a full authentication system in your app:

**Models:**
- `models/concerns/authenticable.py` - mixin that adds login/password fields
- `models/user.py` - User model
- `models/session.py` - Session model

**Controllers:**
- `controllers/sign_up_controller.py` - user registration
- `controllers/session_controller.py` - login/logout
- `controllers/password_reset_controller.py` - password reset flow

**Forms:**
- `forms/sign_up.py` - registration form
- `forms/session.py` - sign-in form
- `forms/password_reset.py` - password reset and change forms
- `forms/auth/validators.py` - validation helpers
- `forms/auth/pwned.py` - "Have I Been Pwned?" checker

**Other:**
- `config/auth.py` - configuration
- `cli/auth_cli.py` - CLI commands for user management
- `emails/password_reset_email.py` - password reset email
- Templates for sign-up, sign-in, password reset, and email

The installer also:

- Adds the framework's `Authentication.for_session(Session)` to your `AppController` concerns
- Installs `passlib`, `argon2-cffi`, and `confusable-homoglyphs` as dependencies
- Creates a `"users"` database migration


## Configuration

Auth settings go in `config/auth.py`:

```python
from proper.units import HOURS

AUTH_HASH_NAME = "argon2"       # Password hashing algorithm
AUTH_ROUNDS = None              # None = use the default for the algorithm
AUTH_PASSWORD_MINLEN = 9        # Minimum password length
AUTH_PASSWORD_MAXLEN = 1024     # Maximum password length (DoS prevention)
AUTH_TOKEN_LIFE = 3 * HOURS     # Password reset token lifetime (seconds)
```

### Supported Hash Algorithms

| Algorithm        | Notes                                    |
|------------------|------------------------------------------|
| `argon2`         | Recommended. Memory-hard, modern.        |
| `bcrypt`         | Widely used, battle-tested.              |
| `bcrypt_sha256`  | Bcrypt with SHA-256 pre-hash.            |
| `pbkdf2_sha512`  | Core default. No native dependencies.    |
| `pbkdf2_sha256`  | PBKDF2 with SHA-256.                     |
| `sha512_crypt`   | System-level crypt.                      |
| `sha256_crypt`   | System-level crypt.                      |

If you change the hash algorithm after users have already registered, their passwords are automatically re-hashed with the new algorithm on their next successful login.


## The User Model

The generated User model inherits from the `Authenticable` mixin:

```python
import peewee as pw

from .base import BaseModel
from .concerns.authenticable import Authenticable


class User(Authenticable, BaseModel):
    created_at = pw.DateTimeField(default=pw.utcnow)
```

The `Authenticable` mixin adds:

### Fields

- `login` - a unique, indexed `CharField` for the email or username
- `password` - a `CharField` that stores the hashed password

### Properties

- `email` - returns the `login` value (convenience alias)

### Class Methods

```python
# Normalize a login (casefold, strip whitespace, SASL-prep)
User.normalize_login("Alice@Example.COM")     # "alice@example.com"

# Create a user (password is hashed, login is normalized)
user = User.create(login="alice@example.com", password="s3cret!pw")

# Look up by primary key
user = User.get_by_id(42)

# Look up by login (normalized)
user = User.get_by_login("Alice@Example.COM")

# Authenticate with credentials (returns user or None)
user = User.authenticate(login="alice@example.com", password="s3cret!pw")
```

### Instance Methods

```python
# Generate a password reset token
token = user.generate_token_for("password_reset")

# Resolve a password reset token (returns user or None)
user = User.resolve_token_for("password_reset", token, max_age=3 * HOURS)

# Set a new password (hashes it)
user.set_password("new-password")
user.save()
```

Token generation and resolution are provided by `ProperModel` (see [Token Generation](models.md#token-generation)). The `Authenticable` mixin defines `generate_token_for_password_reset()`, which returns a fragment of the password hash as a fingerprint. This means password reset tokens are automatically invalidated when the password changes.

### Login Normalization

Logins are normalized using [SASL-prep](https://tools.ietf.org/html/rfc4013) to prevent username confusion attacks. This includes Unicode NFKD normalization, case-folding, and space removal. For example, `"  Alice@Example.COM  "` and `"alice@example.com"` are treated as the same login.


## The Session Model

Sessions track authenticated users across requests. Each session is a database record with a cryptographically random token:

```python
class Session(BaseModel):
    token = pw.CharField(max_length=43, unique=True, index=True)
    created_at = pw.DateTimeField(default=pw.utcnow)
    expires_at = pw.DateTimeField()
    last_seen_at = pw.DateTimeField(default=pw.utcnow)
    ip_address = pw.IPField(null=True)
    user_agent_hash = pw.CharField(max_length=64)
    user = pw.ForeignKeyField(User, backref="sessions", on_delete="CASCADE")
    revoked = pw.BooleanField(default=False)
```

### Session Lifetime

- **Remember sessions** (default): 60 days
- **Non-remember sessions**: 24 hours

### Key Methods

```python
# Create a session for a user
session = Session.create_for_user(
    user=user,
    ip_address="1.2.3.4",
    user_agent="Mozilla/5.0...",
    remember=True,              # 60 days (default) or 24 hours
)

# Find a valid session by token
session = Session.find_by_token(token)  # None if revoked or expired

# Update activity timestamp
session.touch()

# Revoke a session (soft delete)
session.revoke()

# Check validity
session.is_valid()  # not revoked and not expired
```

Tokens are 256-bit cryptographically random values encoded as URL-safe base64 (43 characters). The User-Agent header is stored as a SHA-256 hash.


## The Authentication Concern

The `Authentication` concern is provided by the framework (`proper.concerns.Authentication`) and bound to your app's `Session` model via the `for_session(Session)` factory. The installer adds it to `AppController`, where it registers a `before` callback that runs on every request, requiring authentication by default:

```python
from proper import Controller
from proper.concerns import Authentication, OriginProtection, RateLimiting

from ..models import Session
from .concerns.form_validation import FormValidation
from .concerns.security_headers import SecurityHeaders


class AppController(
    Controller,
    Authentication.for_session(Session),
    OriginProtection,
    RateLimiting,
    FormValidation,
    SecurityHeaders,
):
    pass
```

To customize a method (e.g. `new_session_for`), override it on `AppController` rather than editing the framework concern.

### How It Works

On every request, `require_authentication` runs as a `before` callback:

1. If `skip_authentication` is `True`, allow the request.
2. If the user is already authenticated (session resumed from cookie), allow the request.
3. If the current action is listed in `skip_authentication`, allow the request.
4. Try to resume the session from the `_auth` signed cookie.
5. If no valid session is found, store the current URL in the session and redirect to the login page.

### Skipping Authentication

To make specific controllers or actions publicly accessible, use `skip_authentication`:

```python
# Skip authentication for the entire controller
class PublicController(AppController):
    skip_authentication = True

# Skip authentication for specific actions only
class ArticlesController(AppController):
    skip_authentication = ("index", "show")
```

### Authentication Methods

These methods are available in any controller that includes the `Authentication` concern:

```python
# Check if the current request is authenticated
self.is_authenticated()         # True/False

# Create a new session and set the auth cookie
self.new_session_for(user)

# Destroy the current session and clear the auth cookie
self.terminate_session()

# Redirect to the URL the user was trying to access before login
self.redirect_after_authentication(default="/", flash="Welcome back!")
```

### The Auth Cookie

The session token is stored in a signed cookie named `_auth`:

- **HttpOnly** - not accessible from JavaScript
- **Secure** - only sent over HTTPS (when the request is secure)
- **SameSite=Lax** - CSRF protection
- **Signed** - tamper-proof via the app's secret keys

### Global Context

The authenticated user and session are available anywhere via the global context:

```python
from proper import current

current.user            # The authenticated User instance (or None)
current.auth_session    # The current Session instance (or None)
```


## Sign-Up

The generated `SignUpController` handles user registration:

| HTTP     | PATH       | ACTION   | USED FOR
| -------- | ---------- | -------- | --------------------
| GET      | /sign-up   | new      | Show the registration form
| POST     | /sign-up   | create   | Create a new user account

### Registration Flow

1. User visits `/sign-up` (GET) — the registration form is rendered.
2. User submits login (email) and password (twice) (POST).
3. The `SignUpForm` validates: checks the login is not already taken, the password meets minimum length, is not pwned, and both passwords match.
4. On success: a new `User` is created, a session is started, and the user is redirected to their original destination (or home) with a "Welcome!" flash.
5. On failure: the form is re-rendered with error messages.

If the user is already authenticated, they are redirected with a "Welcome back!" message (via the `redirect_if_authenticated` before callback).

### Rate Limiting

The `SignUpController` has built-in rate limiting:

- **10 requests** per 15 minutes
- **30 requests** per hour

### Authentication

The entire controller skips authentication (`skip_authentication = True`) since unauthenticated users need access to register.


## Login and Logout

The generated `SessionController` handles sign-in and sign-out:

| HTTP     | PATH       | ACTION   | USED FOR
| -------- | ---------- | -------- | --------------------
| GET      | /sign-in   | new      | Show the login form
| POST     | /sign-in   | create   | Authenticate the user
| DELETE   | /sign-out  | delete   | Log out

### Login Flow

1. User visits `/sign-in` (GET) - the login form is rendered.
2. User submits login and password (POST).
3. The `SignInForm` validates: checks the login exists, then authenticates.
4. On success: a new session is created, the rate limit counter is reset, and the user is redirected to their original destination (or home).
5. On failure: the form is re-rendered with error messages.

If the user is already authenticated, they are redirected with a "Welcome back!" message.

### Logout Flow

1. User sends a DELETE request to `/sign-out`.
2. The session is deleted from the database.
3. The `_auth` cookie is cleared.
4. The session data is cleared to prevent data leaking between users.
5. The user is redirected to `/`.

### Rate Limiting

The `SessionController` has built-in rate limiting to prevent brute-force attacks:

- **Per-login**: 8 attempts per 15 minutes per login (normalized)
- **Per-IP**: 50 attempts per hour (global)

When the per-login limit is exceeded, the user is redirected with an error flash message suggesting they reset their password.


## Password Reset

The generated `PasswordResetController` handles the full password reset flow:

| HTTP     | PATH                        | ACTION  | USED FOR
| -------- | --------------------------- | ------- | --------------------------------
| GET      | /password-reset/new         | new     | Show the "forgot password" form
| POST     | /password-reset             | create  | Send the reset email
| GET      | /password-reset/sent        | show    | Confirmation page
| GET      | /password-reset/:token/edit | edit    | Show the "new password" form
| PATCH    | /password-reset/:token      | update  | Save the new password

### Reset Flow

1. User visits `/password-reset/new` and enters their email.
2. The `PasswordResetForm` validates the login exists.
3. A `PasswordResetEmail` is sent asynchronously with a token generated via `user.generate_token_for("password_reset")`.
4. The user is redirected to a confirmation page.
5. When the user clicks the link, `User.resolve_token_for("password_reset", token)` validates the token.
6. If the token is valid, the user sees a password change form.
7. The `PasswordChangeForm` validates the new password (minimum length, not pwned, passwords match).
8. The password is updated, a new session is created, and the user is logged in.

### Token Security

Password reset tokens use the named token API built into `ProperModel`. The `Authenticable` mixin defines `generate_token_for_password_reset()` which embeds a fingerprint derived from the password hash. The token is signed with the app's secret keys.

The fingerprint ensures the token is automatically invalidated when the password changes. Tokens expire after `AUTH_TOKEN_LIFE` (default: 3 hours). All configured secret keys are tried when validating, supporting key rotation.

### Password Validation

New passwords are validated with:

1. **Minimum length** - configurable via `AUTH_PASSWORD_MINLEN` (default: 9)
2. **Pwned check** - queries the [Have I Been Pwned](https://haveibeenpwned.com/API/v3) API using k-anonymity (only the first 5 characters of the SHA-1 hash are sent). Falls back to a built-in list of common passwords if the API is unreachable.
3. **Confirmation** - passwords must match.

### Rate Limiting

The password reset form is rate-limited to 10 requests per 15 minutes to prevent email flooding.


## Forms

### SignUpForm

```python
class SignUpForm(f.Form):
    login = f.TextField()
    password1 = f.TextField()
    password2 = f.TextField()
```

Validates that the login is not already taken, the password meets minimum length, is not pwned, and both passwords match. Returns a plain dict from `form.save()` (no `Meta.orm_cls`) — the controller creates the `User` explicitly.

### SignInForm

```python
class SignInForm(f.Form):
    login = f.TextField()
    password = f.TextField()
```

Validates that the login exists and the password is correct. By default, it tells the user specifically whether the login or password is wrong. Comments in the generated code show how to switch to a generic "Invalid username and/or password" message.

### PasswordResetForm

```python
class PasswordResetForm(f.Form):
    login = f.TextField()
```

Validates that the login exists. Like the sign-in form, you can edit it to show a generic message instead.

### PasswordChangeForm

```python
class PasswordChangeForm(f.Form):
    password1 = f.TextField()
    password2 = f.TextField()
```

Validates the new password (length, pwned, match).

### Customizing Error Messages

All auth forms share a common message dictionary in `forms/auth/validators.py`. Edit the `MESSAGES` dict to customize:

```python
MESSAGES = {
    "login": "We don't recognize that username. Want to try another?",
    "login-taken": "This username is already registered.",
    "password": "Password doesn't match the username.",
    "auth": "Invalid username and/or password.",
    "new-password-pwned": "This password is too easy to guess.",
    "password-too-short": "Your password must be at least {minlen} characters long",
    "passwords-mismatch": "Passwords don't match.",
}
```


## CLI Commands

The auth blueprint adds CLI commands for user management:

```bash
# Create a new user
myapp auth user alice@example.com "s3cret-password"

# Update a user's password
myapp auth password alice@example.com "new-password"
```

Replace `myapp` with your app's command name. The password is hashed automatically.


## Security Features

### Password Security

- **Argon2 by default** - memory-hard hashing algorithm resistant to GPU attacks
- **Unicode normalization** - passwords are SASL-prepped to prevent encoding-based bypasses
- **Automatic hash upgrades** - when you change the hash algorithm, passwords are re-hashed on next login
- **Timing attack prevention** - a decoy password is verified even when the user doesn't exist, preventing timing-based user enumeration
- **DoS prevention** - passwords longer than `AUTH_PASSWORD_MAXLEN` (1024 chars) are rejected before hashing

### Session Security

- **256-bit random tokens** - cryptographically secure, URL-safe
- **Signed cookies** - tokens are stored in signed cookies to prevent tampering
- **HttpOnly + SameSite=Lax** - prevents XSS-based cookie theft and most CSRF attacks
- **Absolute expiration** - sessions expire at a fixed time, not relative to last activity
- **Session revocation** - sessions can be explicitly revoked (soft delete)
- **IP and User-Agent tracking** - stored for audit purposes

### Token Security

- **Signed** - tokens are signed with the app's secret keys via `app.dumps()` and cannot be forged
- **Time-limited** - tokens expire after a configurable `max_age`
- **Fingerprinted** - the `Authenticable` mixin includes a password-derived fingerprint, so changing the password invalidates all outstanding tokens
- **Key rotation** - all secret keys are tried when validating, allowing gradual key rotation


## Full Authentication Flow

### Sign-Up

```
GET /sign-up              # 1. User sees the registration form
POST /sign-up             # 2. User submits login + password + confirmation
  -> SignUpForm validates  # 3. Check login available, password strong, passwords match
  -> User.create()         # 4. Create user (password hashed)
  -> new_session_for()     # 5. Create Session, set _auth cookie
  -> redirect_after_auth() # 6. Redirect to home with "Welcome!"
```

### Login

```
GET /sign-in              # 1. User sees the login form
POST /sign-in             # 2. User submits login + password
  -> SignInForm validates  # 3. Check login exists, verify password
  -> new_session_for()     # 4. Create Session, set _auth cookie
  -> redirect_after_auth() # 5. Redirect to original page or home
```

### Authenticated Request

```
Any request               # 1. Request arrives
  -> require_authentication  # 2. before callback runs
  -> _find_session_by_cookie # 3. Read _auth signed cookie
  -> Session.find_by_token   # 4. Look up session (not revoked, not expired)
  -> session.touch()         # 5. Update last_seen_at
  -> set current.user        # 6. Make user available globally
  -> action executes         # 7. Controller action runs with authenticated user
```

### Logout

```
DELETE /sign-out           # 1. User clicks logout
  -> terminate_session()   # 2. Delete session from DB
  -> clear _auth cookie    # 3. Remove signed cookie
  -> clear session data    # 4. Prevent data leaking
  -> redirect to /         # 5. Send user home
```

### Password Reset

```
GET /password-reset/new             # 1. User enters email
POST /password-reset                # 2. Validate, send email with token
GET /password-reset/sent            # 3. Show "check your email"
GET /password-reset/:token/edit     # 4. User clicks link, validate token
PATCH /password-reset/:token        # 5. Set new password, create session
  -> redirect_after_auth()          # 6. Redirect to home, logged in
```
