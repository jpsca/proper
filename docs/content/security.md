---
title: Security
description: |
  What Proper does to protect your application and what you have to do yourself. Covers CSRF, XSS and the Content Security Policy, sessions and secret keys, passwords, rate limiting, authorization, input, HTTPS and proxies, security headers, WebSockets, and errors in production.
number_headers: true
---

# Security

An application on the public internet gets requests from people who want to read data that isn't theirs, act as another user, or run their code in your users' browsers. Proper turns on a set of protections in every new application, so most of the common attacks fail without you doing anything. Other protections depend on decisions only you can make: who may see a record, which HTML is safe to show unescaped, which URL a redirect can go to.

This guide is about both: what each attack is, what Proper does about it, and what is left for you. The details of each feature are in its own guide; this one links to them.

After reading this guide, you will know:

- Which protections are on by default, and where they live in your app.
- How Proper stops cross-site request forgery without tokens.
- Where escaping protects you from XSS and where it doesn't, and how to add a Content Security Policy.
- How sessions, cookies and secret keys work, and how to rotate the keys.
- What to rate limit, and how.
- What you must check yourself: authorization, redirects, raw SQL.
- What to verify before deploying.

---

## What Proper does for you

Protection                         | On by default? | Where it lives
---------------------------------- | -------------- | ----------------------------------------------------
CSRF: origin checks                | Yes            | `OriginProtection`, in `AppController`
XSS: escaping in templates         | Yes            | Every `{{ ... }}` in a Jx template
XSS: sanitizing rich text          | Yes            | The rich text addon, when it renders a document
Uploaded files can't run scripts   | Yes            | The storage addon, when it serves a file
Signed session and auth cookies    | Yes            | Every request
Password hashing (argon2)          | Yes            | The auth addon
Rate limits on sign-in, sign-up and password reset | Yes | The controllers of the auth addon
Request size limits                | Yes            | `MAX_CONTENT_LENGTH` and the other `MAX_*` settings
Security headers                   | Yes            | `SecurityHeaders`, in `AppController`, a file of your app
WebSocket origin checks            | Yes            | The cable
Content Security Policy            | No             | You add it to `SecurityHeaders` (see [below](#content-security-policy))
Authorization                      | No             | Your controllers and models

And what no framework can do for you:

- **Decide who may see what.** Proper knows who the user is; only your code knows whether that user may read invoice 42. See [Authorization](#authorization).
- **Know which HTML is safe.** If you mark a value as safe, Proper doesn't escape it.
- **Know which URLs are yours.** A redirect to a URL taken from the request can send your users anywhere.

---

## Cross-site request forgery

A cross-site request forgery (CSRF) is a request that another site makes the user's browser send to your application. The browser adds your cookies to it, so your application sees a signed-in user asking to change their email, transfer money, or delete their account, while the user only opened a page of another site.

### How `OriginProtection` decides

Browsers tell the server where a request comes from: the `Origin` header has the site of the page that sent it, and the `Sec-Fetch-Site` header says whether that site is the same as the one the request goes to. `OriginProtection` reads them, so it needs no hidden tokens in forms. For each request it follows these steps, in order, and stops at the first that applies:

1. A `GET`, `HEAD`, `OPTIONS` or `QUERY` request is allowed. These methods must not change anything.
2. A request with neither `Origin` nor `Sec-Fetch-Site` is allowed. Browsers send at least one of them with every state-changing request, so this one doesn't come from a browser, and only browsers add the user's cookies on their own.
3. A request whose `Origin` is in the `TRUSTED_ORIGINS` setting is allowed.
4. If `Sec-Fetch-Site` is present: `same-origin` or `none` (the user typed the URL, or used a bookmark) is allowed; any other value is refused. This protects every current browser on HTTPS or `localhost`.
5. A request whose `Origin` host and port are the same as its `Host` is allowed. This is a request over plain HTTP, or from an old browser.
6. A request whose `Origin` and `Host` are both on the local network (a private, loopback or link-local address) is allowed, so you can test from a phone on your LAN.
7. Any other request is refused with `InvalidOrigin`, a `403 Forbidden`.

`OriginProtection` is mixed into the `AppController` of every new application, so every controller has it.

### Trusting other sites

If another site of yours must be able to post to your application, list it in `TRUSTED_ORIGINS`, with its protocol, and its port if it isn't the default:

```python {title="config/main.py"}
TRUSTED_ORIGINS = [
    "https://admin.example.com",
    "https://partners.example.com:8443",
]
```

Only list sites you control. A page on a trusted origin can make your users' browsers do anything they can do.

### A `GET` must not change anything

Step 1 allows every `GET`, `HEAD`, `OPTIONS` and `QUERY`. If one of your actions changes data on a `GET` (a "delete" link, an "unsubscribe" link that unsubscribes when it is opened), any site can trigger it with an `<img src="...">`. Use `POST`, `PATCH`, `PUT` or `DELETE` for every action that changes something. Proper's resource routes already do: only `index`, `show`, `new` and `edit` are `GET`s.

For a link that must work from an email, like "unsubscribe", make the `GET` show a page with a button, and make the button `POST`.

### SameSite cookies

The session cookie is sent with `SameSite=Lax` (the `SESSION_COOKIE_SAMESITE` setting), so browsers don't add it to a `POST` from another site. This is a second layer, behind `OriginProtection`: don't set it to `None` unless you need the session in requests from other sites.

### Token-based protection

Before browsers sent `Sec-Fetch-Site`, the defense against CSRF was a secret token, stored in the session and sent back with every form. Proper still has it, as the `RequestForgeryProtection` concern, for the rare application that must support browsers older than 2020 over plain HTTP. To use it, replace `OriginProtection` with it in your `AppController`:

```python {title="controllers/app_controller.py"}
from proper.concerns import RequestForgeryProtection

class AppController(
    RequestForgeryProtection,
    ...
)
```

Then every state-changing request must send the token: as a `csrf_token` form field, or in an `X-CSRF-Token` header for requests made with JavaScript. The token of the current request is in `current.csrf_token`:

```html
<form method="post" action="{{ url_for('Comment.create') }}">
  <input type="hidden" name="csrf_token" value="{{ current.csrf_token }}">
  ...
</form>
```

A request without the token, or with a wrong one, is refused with a `403`. The token also goes in the `X-CSRF-Token` header of every response, so JavaScript can read it from there.

---

## Cross-site scripting

In a cross-site scripting attack (XSS), someone gets their JavaScript into a page of your application: as a comment, a name, a search term in the URL. When another user opens the page, the script runs as if it were yours, with access to everything that user can see and do.

### Escaping in templates

Jx escapes every value you output with `{{ ... }}`: `<`, `>`, `&`, `"` and `'` become HTML entities, so a comment that says `<script>alert(1)</script>` shows as text. You don't have to do anything for this.

The escaping is turned off in two cases, and both are your decision:

- **The `|safe` filter:** `{{ comment.body | safe }}` outputs the value as it is.
- **`Markup` objects:** a value wrapped in `markupsafe.Markup` (in Python) is output without escaping.

Use them only for HTML your code made, never for something a user wrote, or wrote part of. If you build HTML in Python with values from users, escape them first with `markupsafe.escape()`, or use `Markup.format()`, which escapes its arguments.

Escaping makes a value safe as text in HTML. It doesn't make it safe everywhere:

- **URLs in attributes.** `<a href="{{ user.website }}">` is escaped, but a website of `javascript:alert(1)` still runs when clicked. Check that a URL from a user starts with `https://` or `http://` before you save it.
- **Data inside `<script>`.** To pass data to JavaScript, use the `|tojson` filter, which escapes `<`, `>`, `&` and `'` so the value can't close the `<script>` tag. Better yet, put it in a `data-` attribute and read it from a Stimulus controller.
- **Event handler attributes** like `onclick="..."` run their content as JavaScript. Don't put values there.

### Rich text

The rich text addon stores the HTML that the editor sends, and anyone can send any HTML. So the HTML is sanitized every time a document is rendered: only the tags, attributes, CSS properties and URL schemes of an allowlist are kept. `{{ post.body }}` is sanitized; `post.body.to_html()` isn't. See [Sanitizing](/docs/rich_text#sanitizing) in the Rich Text guide.

### Uploaded files

A user can upload an HTML or SVG file with a script in it. If your application serves it from your domain, and the browser shows it, the script runs on your domain. The storage addon prevents that:

- Only the content types in `STORAGE_ALLOWED_INLINE` are shown in the browser: images, videos and PDFs, by default. Every other file is downloaded.
- Every file it serves has `X-Content-Type-Options: nosniff`, so the browser uses the stored content type and doesn't guess another one from the bytes.
- Every file it serves, except PDFs, has a `Content-Security-Policy` with `sandbox`: even an image shown in the browser is a document without scripts and without access to your domain.
- Image variants are made only with the image loaders in a short allowlist. The SVG loader, which can read local files, and the ImageMagick loader, which can run commands, are not in it.

If you serve uploaded files with your own code, set the same headers.

### Content Security Policy

A Content Security Policy (CSP) is a response header that tells the browser where scripts, styles, images and other resources may come from. It is a second line of defense: if an attacker gets HTML into a page, the browser refuses to load anything the policy doesn't allow.

New applications don't send one, because the right policy depends on what your application loads. Add it to your `SecurityHeaders` concern:

```python {title="controllers/concerns/security_headers.py" hl_lines="4-14 21"}
from proper import Concern
from proper.units import YEARS

CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    # The import map that `render_importmap` writes is an inline script
    "script-src 'self' 'unsafe-inline'",
    # Turbo's progress bar is an inline style
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
])


class SecurityHeaders(Concern):
    after = {"do": "set_security_headers"}

    def set_security_headers(self):
        headers = self.response.headers
        headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        ...
```

The headers are set with `setdefault`, so a response that already has the header keeps its own. This matters here: the storage addon sends a stricter policy with every file it serves, and it must not be replaced.

Adjust the policy to your application:

- **Files in S3 or another service.** A private file is served with a redirect to the service, so the browser loads it from there: add the service's domain to `img-src` (and to `media-src`, for videos).
- **The cable on its own port.** If `CABLE_PORT` is set, add the cable's URL to `connect-src`, like `connect-src 'self' wss://example.com:2301`.
- **Scripts or fonts from a CDN.** Add the CDN's domain to `script-src` or `font-src`.

To try a policy without breaking pages, send it first as `Content-Security-Policy-Report-Only`. The browser then only reports what it would block, in its console, and you can fix the policy before you enforce it.

:::warning | Why `'unsafe-inline'` in `script-src`
`render_importmap` writes the import map as an inline `<script type="importmap">`, and without it the browser can't load Turbo, Stimulus, or your JavaScript. A policy can allow an inline script in three ways: with `'unsafe-inline'`, with the hash of the script, or with a *nonce*, a random value made for each response that the script must carry. Proper has no nonces yet, and the hash changes every time an asset changes, because the import map has the fingerprinted URLs. So the policy above allows inline scripts.

This means the policy doesn't stop a `<script>` an attacker manages to put in a page. It still stops scripts from other domains, plugins (`object-src`), a `<base>` tag that changes where relative URLs go (`base-uri`), forms that send data to other sites (`form-action`), and other sites from framing yours (`frame-ancestors`). Escaping is still your main defense against XSS.
:::

---

## Sessions, cookies, and secret keys

### The session cookie

The session (`request.session` and `response.session`) is stored in the user's browser, in a cookie named `_session`. The cookie is **signed**, so the user can't change it: Proper ignores a session whose signature doesn't match. It isn't **encrypted**, so the user can read it. Don't put anything in the session that the user must not see.

The cookie is sent with these attributes:

Attribute  | Value                                       | Setting
---------- | ------------------------------------------- | -------------------------
`HttpOnly` | Yes: JavaScript can't read it               | `SESSION_COOKIE_HTTPONLY`
`SameSite` | `Lax`: not sent in a `POST` from another site | `SESSION_COOKIE_SAMESITE`
`Secure`   | When the request came over HTTPS            | (automatic)
`Max-Age`  | 30 days                                     | `SESSION_COOKIE_LIFETIME`

The `Secure` attribute depends on `request.is_secure`. Behind a proxy that receives HTTPS and talks HTTP to your application, that is only true if the proxy is in `TRUSTED_PROXIES` and sends `X-Forwarded-Proto`. See [HTTPS and proxies](#https-and-proxies).

### The auth session

The auth addon doesn't keep the signed-in user in the session cookie. When a user signs in, it creates a row in the `session` table and sends a random token that points to it in an `_auth` cookie, also signed. So:

- **A session can be revoked**, and the revocation is immediate: the next request with that cookie has no user. `session.revoke()` signs out one browser.
- **A session expires**, 24 hours after signing in, or 60 days with "remember me", whatever the user does.
- **Changing the password signs out every other browser and device** of that user, so someone who had the old password, or a session made with it, loses access.

See [The Auth Session](/docs/authentication#the-auth-session) in the Authentication guide.

### Secret keys

Proper signs the session and auth cookies, the tokens of password reset links, the URLs of private files, and anything you sign with `app.dumps()`, with the keys in `SECRET_KEYS`. Anyone who has a key can make all of those, including a cookie that signs them in as any user. So:

- **Each key must be random and at least 48 characters long.** Proper refuses to start with a shorter one. Make one with:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

- **Keep the production keys out of your code.** New applications read them from the `SECRET_KEYS` environment variable in production, separated by commas. The key in `config/main.py` is for development only.

The list goes from oldest to newest. Proper signs with the newest, the last one, and accepts a signature made with any of them. That lets you change keys without signing everybody out:

1. Add a new key at the end of the list, and deploy.
2. Wait until what was signed with the oldest key has expired: 30 days for the session cookie, 60 days for a "remember me" auth session.
3. Remove the oldest key, and deploy.

Remove a key at once, without waiting, if it may have leaked: everyone is signed out, and every password reset link and private file URL made with it stops working, but whoever has the key can't use it anymore.

---

## Passwords and accounts

These are the protections of the [auth addon](/docs/authentication). The code is in your application, so you can change any of them.

- **Passwords are hashed with argon2**, an algorithm made to be slow to guess. If you change the algorithm (`AUTH_HASH_NAME`) or its cost (`AUTH_ROUNDS`), each password is hashed again the next time its user signs in.
- **New passwords are checked against known leaks.** The sign-up and password change forms reject a password that appears in the "Have I Been Pwned" database. The password never leaves your server: only the first 5 characters of its SHA-1 hash are sent.
- **Passwords have a minimum and a maximum length**, 9 and 1024 characters by default (`AUTH_PASSWORD_MINLEN`, `AUTH_PASSWORD_MAXLEN`). The maximum exists because hashing is slow on purpose: a password of several megabytes would keep a thread busy.
- **Logins are normalized** before they are saved or looked up: lowercased, without spaces, and with the Unicode variants of a character folded into one, so nobody can register `ＡＤＭＩＮ` (with full-width letters) next to `admin`.
- **Logins are ASCII.** Letters of other alphabets can look like Latin ones, so the sign-up form refuses a login with any letter that isn't ASCII: `аdmin`, with a Cyrillic `а`, can't pass for `admin`. The international domain of an email is accepted, written in punycode (`münchen.de` is `xn--mnchen-3ya.de`). See [The Sign-Up Form](/docs/authentication#the-sign-up-form).
- **Password reset links expire** after 3 hours (`AUTH_TOKEN_LIFE`), and stop working as soon as the password changes, so a link can be used only once.

Two decisions are yours:

- **Revealing or hiding which accounts exist.** By default, the sign-in and password reset forms say when there is no account with that email. That's friendlier, but it lets anyone check whether an email has an account, a few at a time because of the rate limits. For applications where having an account is sensitive in itself (health, dating, legal help), hide it. See [Revealing vs Hiding Account Existence](/docs/authentication#revealing-vs-hiding-account-existence).
- **What the addon doesn't include.** There is no multi-factor authentication and no email confirmation: a new user is signed in right away, with an email nobody checked. If your application sends email to the addresses users give, or trusts them, confirm them first.

---

## Rate limiting

Without limits, an attacker can try thousands of passwords per minute against one account, or one common password against thousands of accounts. Rate limits make that slow enough to be useless. The `RateLimiting` concern is in every `AppController`; it does nothing until a controller sets `rate_limit`. The [Controllers Advanced guide](/docs/controllers_advanced#rate-limiting-the-hard-cases) explains all its options; this section is about what to limit.

### What the auth addon limits

The controllers of the auth addon come with these limits:

Action                  | Limit                          | By
----------------------- | ------------------------------ | ----------------
Sign in                 | 8 attempts in 15 minutes       | The login (email)
Sign in                 | 50 attempts in 1 hour          | IP address
Sign up                 | 10 in 15 minutes, 30 in 1 hour | IP address
Password reset request  | 10 in 15 minutes               | IP address

The sign-in has two limits because each stops a different attack. The limit by login stops many guesses against one account, from many addresses. The limit by IP stops one address from trying a few passwords against many accounts. After a successful sign-in, the limit of that login is reset, so a user who mistyped their password a few times doesn't stay locked out.

### What to limit in your application

Limit the actions where each request costs you something or gives an attacker something:

- **Anything that checks a secret:** a code sent by SMS or email, an invitation code, a coupon. Limit by what is being guessed (the invitation, the user) and by IP.
- **Anything that sends something:** emails, SMS, notifications, invitations. Each one costs money and can be used to spam others.
- **Expensive actions:** exports, reports, searches without an index.
- **API endpoints**, limited by token, or by user, not by IP.

Leave the rest alone. Pages that only show data, and assets, don't need limits; caching them is a better defense against load.

### Choosing what to limit by

The default is the IP address. When you limit by something else, with the `by` option, remember that the client chooses it. A limit by email, alone, lets an attacker send as many requests as they want, each with a different email. Keep a limit by IP next to every limit by something the client sends, as the sign-in does.

The IP address is `request.remote_ip`, and it is only right if `TRUSTED_PROXIES` lists your proxies. If it doesn't, every request seems to come from your proxy, and all your users share one limit. See [HTTPS and proxies](#https-and-proxies).

:::warning | Rate limits need a cache
The concern keeps its counters in the cache. Without a cache configured, rate limits are ignored: no error, no warning, no protection. New applications use an SQLite file in production, which every process on that machine shares. If your application runs on several machines, use a cache they share, like Redis, or each machine counts on its own. See the [Caching guide](/docs/caching).
:::

---

## Authorization

Authentication is knowing who the user is. Authorization is deciding what they may do. Proper does the first; the second is always your code, because only your application knows its rules.

The most common mistake is loading a record by the ID in the URL without checking who it belongs to:

```python
def show(self):
    # Anyone signed in can read any invoice, by changing the ID in the URL
    self.invoice = Invoice.find(self.params["id"])
```

Load it from what the user owns instead:

```python
def show(self):
    self.invoice = (
        current.user.invoices
        .where(Invoice.id == self.params["id"])
        .first()
    )
    if self.invoice is None:
        raise NotFound
```

Some guidelines:

- **Answer `404 Not Found`, not `403 Forbidden`**, for a record the user may not see. A `403` tells them that it exists.
- **Check in a `before` callback** when every action of a controller needs the same check, so a new action can't forget it.
- **Check every place that reaches the data**, not only the controllers: private files, channels, background tasks that act for a user. For files, see [Authenticated Controllers](/docs/storage#authenticated_controllers) in the Storage guide; for channels, see [WebSockets](#websockets).

For roles ("admin", "member") and permissions per record, see [Adding Groups and Permissions](/docs/authentication#groups-and-permissions) in the Authentication guide.

---

## Input

### Size limits

Proper refuses requests that are too large before it reads them, so a large request can't fill your server's memory:

Setting              | Default | What it limits
-------------------- | ------- | -----------------------------------------------------------
`MAX_CONTENT_LENGTH` | 8 MB    | The body of a request, files included. Over it: `413`.
`MAX_QUERY_SIZE`     | 1 MB    | The query string. Over it: `414`.
`MAX_FORM_FIELDS`    | 100     | The fields of a form, other than files.
`MAX_FORM_FILES`     | 10      | The files of a form.
`MAX_FORM_PART_SIZE` | 2 MB    | Each field of a form, other than files.

If your application accepts large uploads, raise `MAX_CONTENT_LENGTH` only for that, and make the reverse proxy allow the same size.

### Forms

A form only reads the fields it declares, and `form.save()` only writes those. A user who adds `is_admin=1` to a request doesn't change anything, unless your form has an `is_admin` field. So:

- Don't declare fields that users must not change.
- Values that come from the server, like the current user or the account, go in `form.save(user_id=current.user.id)`, never in a hidden field: a user can change a hidden field.

### SQL

Peewee sends values to the database as parameters, separate from the SQL, so values in queries built with Peewee can't change the query. That stops being true when you write SQL yourself. With `raw()` or `SQL()`, pass the values as parameters, never in the text:

```python
# Wrong: a value of `' OR 1=1 --` returns every user
User.raw(f"SELECT * FROM user WHERE login = '{login}'")

# Right
User.raw("SELECT * FROM user WHERE login = %s", login)
```

The placeholder is `%s` for PostgreSQL and `?` for SQLite. For column names or sort directions that come from the request, which can't be parameters, check them against a list of allowed values.

### Redirects

`redirect_to` follows any `http://` or `https://` URL you give it. If you take that URL from the request, like the `?next=` of a sign-in page, an attacker can send your users a link to your site that ends on theirs, a page that looks like your sign-in and asks for the password again. Before you redirect to a URL from the request, check that it starts with `/`:

```python
next_url = self.params.get("next", "")
if not next_url.startswith("/"):
    next_url = "/"
self.response.redirect_to(next_url)
```

A path that starts with `//` or `/\` is not a problem: `redirect_to` turns them into a single `/`, so `//evil.com` becomes `/evil.com`, a path of your site.

---

## HTTPS and proxies

### HTTPS

Serve your application only over HTTPS. Without it, anyone on the network between your user and your server, on a public Wi-Fi for example, can read and change everything, cookies included.

Proper doesn't handle TLS itself: a reverse proxy in front of it does, like nginx or the load balancer of your hosting. Make the proxy redirect HTTP to HTTPS. Once a browser has visited your site over HTTPS, if you enable the `Strict-Transport-Security` header in the `SecurityHeaders` concerm, it will make it use HTTPS for the `max-age` you set, even for an `http://` link.

### Trusted proxies

Behind a proxy, the connection to your application comes from the proxy, not from the user. The proxy says who the user is, and whether they connected over HTTPS, in headers like `X-Forwarded-For` and `X-Forwarded-Proto`. Any client can send those headers too, so Proper only believes them when the request comes from an address in `TRUSTED_PROXIES`.

The default trusts the loopback, private and link-local networks, which is right when the proxy runs on the same machine or the same private network. If clients can connect to your application from those networks too, or if there is a CDN in front of your proxy, list exactly your proxies. When this setting is wrong:

- With too few proxies: `request.remote_ip` is the address of a proxy for every user, so rate limits by IP put everyone together, and `request.is_secure` is false, so cookies lose the `Secure` attribute.
- With too many: a client can set its own `remote_ip` and get around rate limits by IP.

See [Trusted proxies](/docs/deployment#trusted-proxies) in the Deployment guide.

### The `Host` header

The client chooses the `Host` header of the request. Proper uses it to choose a route and in `OriginProtection`, but never to build a URL: `url_for(..., _full=True)`, the password reset email and the URLs of files use `PROTOCOL` and `HOST` from your config. Do the same: build every absolute URL that leaves the request, in an email or a link sent to others, with `url_for(..., _full=True)`, never with `request.host`. Otherwise an attacker who sends a request with their own domain in `Host` gets a password reset email with a link to it.

---

## Security headers

The `SecurityHeaders` concern of your application, in `controllers/concerns/security_headers.py`, adds these headers to every response:

Header                              | Value                             | What it does
----------------------------------- | --------------------------------- | -------------------------------------------------------
`X-Frame-Options`                   | `SAMEORIGIN`                      | Only your pages can show yours in a frame, so another site can't put a page of yours under an invisible layer and trick users into clicking on it ("clickjacking").
`X-Content-Type-Options`            | `nosniff`                         | The browser uses the `Content-Type` you send and doesn't guess another one, so a text file can't run as a script.
`X-XSS-Protection`                  | `0`                               | Turns off the XSS filter of old browsers. Current browsers don't have one, and the filter itself could be used to leak data from a page.
`X-Permitted-Cross-Domain-Policies` | `none`                            | Adobe products (Flash, Acrobat) can't load data from your site.
`Referrer-Policy`                   | `strict-origin-when-cross-origin` | Other sites only see your domain in the `Referer` header, not the full URL, which may have IDs or tokens.

```python {title="controllers/concerns/security_headers.py"}
from proper import Concern
from proper.units import YEARS


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

The file is part of your application, so you can change it: add a [Content Security Policy](#content-security-policy), enable `Strict-Transport-Security`, etc. Since the headers are set with `setdefault`, a controller can set a different value for its own responses.

---

## WebSockets

A WebSocket is opened with an HTTP request, and the browser sends your cookies with it, even when a page of another site opens it. That's the same problem as CSRF, and the cable has the same kind of solution: it checks the `Origin` of the connection, and refuses connections from other sites, unless they are in `CABLE_ALLOWED_ORIGINS`. See [Checking where a WebSocket comes from](/docs/channels#checking-where-a-websocket-comes-from).

Once connected, the channels know the user, as controllers do. What they don't know is which streams that user may listen to. Check it in `subscribed()`, and reject the subscription when the user doesn't belong to that room, document, or account:

```python
def subscribed(self):
    room = Room.get_or_none(Room.id == self.params["room_id"])
    if room is None or not room.has_member(current.user):
        self.reject()
        return
    self.stream_from(f"room_{room.id}")
```

See [Authorizing versus authenticating](/docs/channels#authorizing-versus-authenticating) in the Channels guide.

---

## Errors in production

With `DEBUG` on, an error shows a debug page with your code, the values of its variables, the request, and your config. It hides what looks like a secret, but it still shows far too much to anybody. New applications only turn `DEBUG` on in development. Check that it stays that way. See [The debug error pages](/docs/controllers_advanced#the-debug-error-pages).

In production, users see your error page instead, and the error goes to the logs. Every response has an `X-Request-ID` header, and every line of the logs has the same ID, so a user can give you that ID and you can find what happened without showing them the error.

---

## Before deploying

- [ ] `DEBUG` is off.
- [ ] `SECRET_KEYS` comes from the environment, and each key is random and at least 48 characters long.
- [ ] The site is only served over HTTPS, and HTTP redirects to HTTPS.
- [ ] `TRUSTED_PROXIES` lists your proxies: check that `request.remote_ip` is the address of a user, not of your proxy.
- [ ] `HOST` and `PROTOCOL` are your public domain and `https`.
- [ ] A cache is configured, shared by every machine, so rate limits work.
- [ ] Every action that loads a record by ID checks that the user may see it.
- [ ] Every action that changes data uses `POST`, `PATCH`, `PUT` or `DELETE`.
- [ ] No `|safe` or `Markup` wraps something a user wrote.
- [ ] No redirect goes to a URL taken from the request without checking it.
- [ ] No raw SQL has values from the request in its text.
- [ ] You decided whether to reveal which accounts exist.
- [ ] You added a Content Security Policy, or decided not to.
