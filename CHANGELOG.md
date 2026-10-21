# Changelog

All notable changes to Proper are documented in this file.

## Unreleased

### ⚠️ Upgrading: Proper writes the logs

The app now puts a handler on the root logger that writes the logs of
every logger (Proper's, yours, peewee's, huey's) to stderr: one line for
people with `DEBUG`, one JSON object per line without it. Each line has
the `request_id` of the request being answered. If your app calls
`logging.basicConfig()` or adds its own handler to the root logger, each
line is now written twice: remove yours, or set `LOG_FORMAT = "off"` to
keep configuring `logging` yourself.

### ⚠️ Upgrading: the `TestClient` raises the errors of the app

An exception of the app that ends in a server error is now raised in the
test, with its real traceback, instead of being answered with a `500` page.
An `HTTPError`, or any exception with a `status`, is still answered, and so
is an error that an error handler answers with a status under 500. A test
that checks an error page needs `TestClient(app, raise_server_errors=False)`.

### Added

- Every request has an ID, `request.request_id`, and every response sends
  it in an `X-Request-ID` header, error pages too. It is the
  `X-Request-ID` header of the request, if it has one (a proxy or a load
  balancer can add it), or a new UUID.
- A task enqueued while a request is answered logs with that request's
  `request_id`, in the worker too, and so do the tasks chained to it and
  its retries.
- `LOG_FORMAT` in the config: `"console"`, `"json"`, or `"off"`. The
  default, `None`, is `"console"` with `DEBUG` and `"json"` without it.
- `url_for` fills a placeholder not given (as an argument or by the
  object) with the route's default for it. The default can be a function
  without arguments, called on each `url_for`. `router.scope()` and
  `router.resource()` take `defaults=` too, given to all their routes
  (on a scope, merged with the defaults of each route), so a tenant in
  the URL is filled in for every link:
  `router.scope("org/:org_id<int>", defaults={"org_id": lambda: current.account.id})`.
  The defaults that aren't placeholders still never go into the URL, and
  `proper check` doesn't report a placeholder with a default as missing.

### Changed

- `request.request_id` is never `None`: without an `X-Request-ID` header
  it is a new UUID. The ID of the header keeps only letters, digits, `-`,
  `_`, and `@` (before, only the non-ASCII characters were removed), so it
  can't break a line of a log.
- `proper.helpers.logger` is a structlog logger (`structlog.stdlib.BoundLogger`).
  It takes the same `%s` arguments as before, and keyword arguments as
  fields of the line: `logger.info("Paid %s", order.id, amount=10)`.
  Proper depends on `structlog`.
- The debug error page shows first the frame of the app where the error
  happened, with the lines around it and its variables, and folds the
  frames of Proper and of the libraries. Its title is the error and the
  request (`POST /orders -> OrderController.create`); a "Copy as text"
  button copies the error as plain text. A client that doesn't ask for
  HTML, like `curl` or an agent, gets that text, and one that asks for
  JSON gets it in a JSON object. The not-found page answers the same
  formats. The page no longer loads Prism.
- Proper no longer depends on `traceback-with-variables`.

### Fixed

- The debug pages didn't escape what they show: a query string like
  `?q=<script>...</script>` ran in the page.
- The debug pages showed most secrets: only `SECRET_KEYS` and keys named
  exactly `password` were masked. Now every config key, variable, form
  field, and header whose name ends with `PASSWORD`, `SECRET`, `TOKEN`,
  `API_KEY`, `COOKIE`, `AUTHORIZATION`, etc. is masked, and so is the
  password of any URL.
- The `AGENTS.md` of a new app said that Proper is an ASGI framework, and
  that `form.save()` returns an unsaved instance. Proper serves WSGI, and
  `form.save()` saves it. It now also says to run `proper check`.

## 0.43.0

### ⚠️ Upgrading: `MAX_FORM_FIELDS` limits urlencoded forms too

An `application/x-www-form-urlencoded` body with more fields than
`MAX_FORM_FIELDS` (100 by default) is a 400, as a multipart one is. Without
a limit, a body of 8 MB of `a=&a=&...` took a second and half a gigabyte of
memory to parse. Raise `MAX_FORM_FIELDS` if a form of the app sends more
fields.

### Added

- `proper check` finds the mistakes of an app before it runs, without
  serving a request or touching the databases: controllers and callbacks
  that can't dispatch, hidden routes, route names used for two paths,
  views that don't compile, fields that hide model methods, models that
  differ from their migrations, migration files that don't run, seeds
  that never run, form fields that the model doesn't have, emails without
  a template, misspelled settings, storage and mailer types that don't
  exist, and incomplete locales. One line per problem, with the file and
  line; it exits with 1 on an error. The checks are in `proper.check`.
- `proper check` also checks the route names given to `url_for` and
  `redirect_to`, in the views and in the Python code of the app: a route
  that doesn't exist (with a suggestion), or a placeholder of its path
  not given.
- `proper check` warns of action names in `only`, `exclude` and
  `skip_authentication` that no controller has (a typo matches nothing),
  and reports `rate_limit` method names that don't exist. When importing
  the app turns the GIL back on, it names the extension module that did.
- `proper check` reports a foreign key to a model that `models/__init__.py`
  doesn't import (the migrations don't make its table), or to a model of
  another database, and a `DeferredForeignKey` that was never resolved.

### Changed

- The views compiler reports every error of the component calls in a
  file (a missing argument, a literal of the wrong type, a component not
  imported), not only the first. A syntax error still stops its file.
- `STORAGE_MAX_IMAGE_PIXELS` (100 million by default): a variant isn't made
  from an image with more pixels, which raises `ImageTooLarge`. A PNG of
  400 KB can declare 20,000 × 20,000 pixels, and decoding it took 400 MB
  or more. The size is read from the header, before the pixels are decoded.

### Fixed

- `proper run` warns when a database has migrations that were not
  applied, naming them. `app.has_migrations_pending()` always returned
  `False`, so the warning never showed; it is now the same check, from
  `proper.models.migrations.pending_migrations()`, which only reads the
  `migratehistory` table. Creating the app no longer checks.
- An email with no body and no template raises `EmailTemplateNotFound`
  (from `proper.emails`) when sent, naming the two templates it looked
  for. It was sent with an empty body.
- `proper db create --db <name>` writes only the models stored in that
  database. It took every model of the app, so the migration of a second
  database also created the tables of the main one.
- A storage `type` can be a subclass of a service, such as a subclass of
  `Disk`. Only the direct subclasses of `Service` were found.
- `skip_authentication = "index"` skips only `index`. A string was tested
  as the letters it contains, so it also skipped an action named `in`.
- The file name in a `Content-Disposition` can't break the header. S3's
  `send_file()` and `service_url()` put the attachment's name between
  quotes as it was, so a name with a `"` added parameters, and
  `Response.send_file()` sent a plain ASCII name without quotes, so a `;`
  in it did the same. Both use the new `content_disposition()` (from
  `proper.core.response.response`): a plain name goes quoted; one with a
  `"`, a backslash, a control character or non-ASCII goes as `filename*`
  (RFC 6266), after an ASCII `filename`.
- `new_session_for()` drops the CSRF token of the cookie session, so the
  signed-in user gets a new one. Someone who could plant the cookie session
  (from a sibling subdomain) knew a token that stayed valid after the
  victim signed in. The rest of the session stays.
- `Catalog.render_string()` keeps the last `max_strings` (256) sources
  compiled, and deletes the files of the ones it drops; it kept every
  source, in memory and on disk. Threads that render a new source at the
  same time compile it once.
- A component's `attrs` refuses an attribute name with a space, a quote,
  `<`, `>`, `/`, `=` or a control character (`ValueError`). Names were
  rendered as they were, so with names from data,
  `attrs={{ {key: 1} }}` with `key='"><script>...'` wrote the script
  into the page.
- An `X-Forwarded-Proto` with several values (`http, https`, or several
  lines) gives the last one, the one the trusted proxy appended. The whole
  value was the protocol, so `is_secure` was false and the session cookie
  lost `Secure`. A value other than `http` or `https` is ignored.
- A connection leaves a stream's presence when the channel that tracked it
  stops, even if another channel of the connection still streams from it.
  Before, the user stayed listed until that other channel ended too. With
  two channels of a connection tracking the same stream, it leaves when
  the last one stops, and `untrack()` of a channel that didn't track the
  stream does nothing.
- The presence changes of a user in a stream reach the cable in the order
  they are made. A tab's leave and the join of the user's next tab, on two
  threads, could reach Redis the other way around: the user was then gone
  from the list, on every machine, while connected.
- The streams a channel starts in `subscribed()` (`stream_from()`, and the
  presence of `track()`) reach the server only once `subscribed()` ends
  without rejecting. With `stream_from()` followed by `reject()`, a client
  got the broadcasts made in between, and the other subscribers saw it
  join and leave. A broadcast made while `subscribed()` runs no longer
  reaches the client being subscribed.
- An anonymous connection (no user, no `key`) can `track()` several
  streams: each call made up a new random key, and the second one raised
  `ValueError` (the connection is already present as another key).
- A stream counts as recovered when its latest epoch is (the last one
  `cable.js` sends). When the server dropped a stream's buffer and started
  another, the client's position in the old one made `recovered` false,
  and the page reloaded its state though nothing was missed.
- A `subscribe` reads one recovery position per epoch, and at most 4 epochs
  per stream (the last 4). Each position was a call that sent the stream's buffer
  again under the lock of every stream: a `subscribe` of 1 MB carrying the
  same position 40,000 times sent millions of frames and held up every
  broadcast.
- A channel action is a method of the app's channel class (or of a class
  between it and `Channel`). Any callable attribute counted: a client could
  call `Session` (the model class) or `app` as an action. A `message` or
  `subscribe` whose `channel` isn't a string or whose `params` isn't an
  object is an `invalid_message` error, and an `action` that isn't a string
  is `invalid_action`; before, each logged a traceback and got no answer.
- `RedisCable`'s listener PINGs Redis every 30 seconds while no message
  comes, with TCP keepalive: a connection that died without closing (a NAT
  that forgot it, a failover) went on returning nothing, and broadcasts
  from the other machines stopped arriving with nothing logged. A message
  in Redis that it can't deliver (valid JSON of another shape, say) is
  logged and skipped; before, it dropped the subscription for a second or
  more, and what was published meanwhile was lost.
- In apps with the `auth` addon, resetting the password signs the user out
  of every other session (`Session.revoke_all_for(user)`), so a stolen
  session stops working. The reset token has a SHA-256 digest of the
  password hash instead of 10 of its characters: the token goes by email,
  signed but not encrypted. For an existing app, apply the changes of
  `models/session.py`, `models/concerns/authenticable.py` and
  `controllers/password_reset_controller.py`; the reset links already sent
  stop working.
- `allowed_ext` of a static route allowed a name with several dots only
  for its whole ending: `jquery.min.js` needed `".min.js"`, and
  `font-1.2.woff2` was a 404 with `".woff2"`. Any ending of the name
  counts now.
- A `%00` in the path of a static file is a 404, not a 500.
- Clearing the session expires the session cookie with its
  `SESSION_COOKIE_PATH` and `SESSION_COOKIE_DOMAIN`. With either set, the
  browser kept the old session cookie, as the expired one had `Path=/` and
  no `Domain`. `unset_cookie()` takes `path` and `domain`.
- `preview_video` runs ffmpeg only on the file itself
  (`-protocol_whitelist file`) and with the demuxers of the new
  `Attachment.VIDEO_FORMATS`. An upload declared `video/*` that was a
  concat playlist made ffmpeg read other files of the server into the
  preview.
- A file served by `attachment.send_file()` is shown in a sandbox
  (`Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline';
  sandbox`) with `X-Content-Type-Options: nosniff`. `image/*` is served
  inline by default, and so was an uploaded SVG with a script: opened by its
  URL, the script ran with the app's origin. PDFs are left out of the
  sandbox, where Chrome's PDF viewer doesn't work.
- A cookie value with a `;` could add attributes to its cookie:
  `set_cookie("theme", "dark; Domain=evil.com")` sent
  `theme=dark; Domain=evil.com; Path=/`. A value with a space, a control
  character, `"`, `,`, `;`, `\` or non-ASCII is now sent quoted, and the
  request reads it back as it was set.
- An error page replaces the body of the response that failed, with the
  headers that describe it. An error after `send_file()` sent the HTML
  page with the file's `Content-Length`, `Content-Type` and
  `Content-Disposition` (a truncated or hanging response), and an error
  after `render(json=...)` sent it as JSON. The error page now goes out
  with the default `Content-Type` and its own length, without the failed
  body's `Cache-Control`, `ETag`, `Expires`, `Last-Modified`, or the
  `x_sendfile_header`, and the file of `send_file()` is closed. The file
  is also closed for a `HEAD` request and a `304`.
- `Response.file_path` is gone: nothing read it.
- Removed code that nothing used: `proper.helpers.cookies` (a copy of
  `proper.core.response.cookies`), and `iter_format_extensions()` and
  `resolve_template()` of `proper.controller.template_resolver`
  (`formats_for()` and `find_template()` do their work).
- `redirect_to()` no longer sends the browser to another site for a path
  that starts with `//` or `/\` (`//evil.com` is `/evil.com`), and
  percent-encodes spaces, control characters and non-ASCII in the URL. A
  redirect route encodes the path values it puts in the `Location` again,
  so `/go//evil.com` with `redirect="/{p}"` stays on the site, and a `%0d%0a`
  in the path can't reach the header.
- The legacy `RequestForgeryProtection` concern now masks its CSRF token
  for real. The masked token was a random prefix followed by the token
  itself, so the token was the same in every response, and a BREACH attack
  could still guess it. Now it is a random one-time pad followed by the
  token XORed with it, in base64 (88 characters instead of 64), and the
  check compares in constant time. Forms rendered before the upgrade carry
  the old token, and fail the check once.

## 0.42.1

### Fixed

- An error raised in an action of a `@router.resource()` controller and
  handled by an error handler of another controller (`@router.error(NotFound)`
  on a `PublicController`) was a 500 in production, with a `ConfigError`
  (`PublicController.not_found` is not the `not_found` action of
  `ArtworkController`) instead of the handler's page. Since 0.40, a resource
  route runs on its own class, and the copy of the route that dispatches to
  the handler kept that class. The handler now runs on the class that
  defines it, as before 0.40.

## 0.42.0

### The views compiler is part of Proper

Proper compiles its views itself: the runtime is `proper.views`, and the
compiler, `jxc`, is built with Proper's native code. The `minijx`
dependency is gone. Code that imports it directly changes
`from minijx import ...` to `from proper.views import ...`. The views an
app compiled before are compiled again when it starts.

### ⚠️ Upgrading: the session is a plain dict

`request.session` and `response.session` are plain dicts, no longer
`DotDict`s: attribute access is gone. Use `session["key"]` or
`session.get("key")` instead of `session.key`, and `session["key"] = value`
instead of `session.key = value`. A request costs 2–3 µs less.

- `proper run` hands each request to the app straight from Bearings, without
  going through WSGI: 6–12% more requests per second. Other servers still
  serve the app over WSGI.
- Signed tokens and cookies (`app.dumps()`, `app.loads()`, the session) are
  made and checked by Proper's own compiled code instead of itsdangerous.
  The tokens are the same: cookies and links made before keep working.
  A request with a session cookie costs about 30% less, and a bad cookie
  is refused six times faster. Signing one (a request that changes the
  session) is about five times faster.
- itsdangerous is no longer a dependency, and `proper.errors.BadSignature`
  no longer inherits from `itsdangerous.BadSignature`.
- Request bodies are parsed by Proper's compiled code: urlencoded forms,
  query strings and multipart/form-data. A form with 3 KB of text or 30
  fields costs a third of what it did, and the fixed cost of an upload
  drops from about 140 µs to 10. A multipart body is checked whole before
  any file is made, so one that is refused leaves no file behind.
- python-multipart is no longer a dependency. As in its 0.0.32, the
  extended parameters of RFC 2231 (`filename*=`, `charset*=`) are ignored,
  as RFC 7578 says for form data.
- HTML is turned into plain text by Proper's compiled code, with one set of
  rules for the text version of an HTML email (`html2text`) and for `str()`
  of a rich text document: 14 times faster for a document, 7 for an email.
  What changes:
  - An image is its `alt` in brackets (`[Logo]`), or nothing without one.
    Before, an email showed its `src` and a document nothing.
  - The text of a document shows the address of its links too:
    `Ver (https://x.com)`.
  - In a document, `<code>` is between backticks and `<pre>` between lines
    of three backticks. `<hr>` is a line of 20 dashes in both.
  - Spaces, tabs and new lines in a row are one space, as a browser shows
    them, except in `<pre>`.
  - The `<title>` of an email is no longer in its text.
  - `proper.rich_text.plain_text` is gone: use
    `proper.helpers.html2text(html, attachments)`.
- `url_for` is three times faster (about 0.7 µs instead of 2.1): each route
  prepares its path once, and a value is encoded or checked for dot
  segments only when it needs it. The URLs are the same.
- Views render about twice as fast. A `url_for` in a view is computed once
  for each route and arguments (str, int or None; with an object, each
  time) and remembered, since it gives the same URL while the app runs. A
  component of one piece returns it without building a list, and the
  whitespace at the start of a component is stripped when the views are
  compiled instead of on every render.
- The view of an action is found without parsing the `Accept` header on
  every request: its formats are remembered per header (up to 256 headers).
  A page with an inferred view is about 5 µs faster.
- Setting a response header costs half of what it did (`set` 0.54 µs →
  0.26, `setdefault` 0.76 → 0.29): a header name is looked up once, and a
  value without parameters is stored as it is. A page that sets the five
  security headers of a new app's `AppController` is about 3 µs faster.

## 0.41.0

### ⚠️ Upgrading: Proper needs Linux

`proper run` now serves with [Bearings](https://github.com/fp-40/bearings), an
HTTP/1.1 server written in Free Pascal, instead of Granian. Bearings runs only
on Linux, so Proper does too: on Windows use WSL, and on macOS a container
(the blueprint's Docker image already is one).

Nothing changes in the app. The settings mean what they did: `WORKERS` is the
number of event loops per process, `MAX_THREADS` the threads that run the app,
`PROCESSES` the copies of the server on the same port.

- `MAX_THREADS` is no longer split between the `WORKERS` of a process: the
  event loops never run Python, and every request runs on one shared pool of
  `MAX_THREADS` threads.
- With `DEBUG`, every request is logged on one line (Combined Log Format).
- The server drops request headers with an underscore in the name
  (`X_Forwarded_For`), which WSGI can't tell apart from the ones with a dash.
- It starts with one line: `[INFO] Listening on 0.0.0.0:2300 (1 workers, 20 threads, pid 1234)`.
- A shutdown no longer waits for idle keep-alive connections.

### ⚠️ Upgrading: the cable is served by Bearings, and RedisCable is back

`proper.channels.Cable` now serves the WebSockets with Bearings, the same
server as the app, instead of proper-wse. Remove `proper-wse` from the app's
dependencies (`uv remove proper-wse`); nothing else changes for the channels,
`cable.js` or the proxy. The test suite of the cable went from two minutes
to 13 seconds.

- Several machines use `RedisCable` again, instead of wse's cluster: the
  `cluster` option is gone, and so is `app.cable.cluster_info()`.
- Presence: `presence_max_data_size` (4 KB) and `presence_max_members` (0)
  bound it, and with `RedisCable` it is one list for all the machines.
- `CABLE_MAX_PENDING_BYTES` (4 MB) is how far behind a client may fall
  before it is closed; `cable.js` reconnects and gets what it missed. It
  must be at least 1. `CABLE_STALL_TIMEOUT` is gone.
- The options `backpressure_bytes`, `backpressure_timeout` and
  `max_outbound_queue_bytes` are gone, and so are wse's own options; an
  unknown option is a `TypeError` at startup. New options: `loops` (4; `0` is one per CPU),
  `max_message` (1 MB, as wse's), `max_subscriptions` (0: no limit),
  `idle_timeout` (60), `recovery_buffer_size` (128), `recovery_ttl` (300),
  `recovery_memory_budget` (256 MB) and `shutdown_grace` (1 second).
- `start_server()` raises `OSError`, with the reason, when the port can't
  be listened on (it raised `RuntimeError`), and a host name that can't be
  looked up is a `socket.gaierror`.
- The metrics are `proper_cable_connections`, `proper_cable_streams` and
  `proper_cable_users`; wse's `wse_*` are gone. `health()["server"]` has
  `connections` and the recovery (`recovery_bytes` among them) and presence
  counters.
- The cable's port answers only the WebSockets on `CABLE_PATH`; any other
  request gets a 404.

## 0.40.0

### ⚠️ Upgrading: the WebSockets need `proper.channels.Cable`

The in-process cable is gone, and with it RSGI: `proper run` always serves
over WSGI, and the only cable that serves WebSockets is
`proper.channels.Cable`, served by proper-wse. It was `WseCable`, in
`proper.channels.wse`, for a few days on `main`; the base class without
WebSockets, what `CABLE = {}` gives, is now `BaseCable`. An app that used
`CABLE = {}` with a `CABLE_PORT` now fails to start with a `ConfigError`.
Install `proper-wse` and set the cable:

```bash
uv add "proper-wse>=2.7.0"
```

```python {title="config/channels.py"}
CABLE = {"type": "proper.channels.Cable"}
```

### ⚠️ Upgrading: `Cable.start_server()` raises when wse can't listen

`Cable.start_server()`, which `proper run` calls before it serves the first
request, now returns only once wse listens on `CABLE_PORT`, and raises
`RuntimeError` when it doesn't:

- at once, with the reason, when wse can't bind the port: the port is taken,
  or the cable's `host` is not an address of this machine or can't be looked
  up (`wse-server could not listen on 0.0.0.0:2301: [Errno 98] Address
  already in use`);
- when wse has neither bound the port nor given up after 10 seconds (a
  machine too busy to run it, a slow lookup of `host`). `start_server()`
  then keeps waiting until wse does one or the other, with no upper limit,
  because wse can't be stopped before it binds; it raises only then, and
  stops wse if it bound late, so nothing is left listening on the port
  when it raises.

Before, `start_server()` returned in those cases with a cable that served
nothing: the app ran, and its WebSockets never connected, or connected to
whatever held the port. Now `proper run` fails to start with that error. An
app that calls `start_server()` itself, under another server, gets the
exception where it calls it: free the port (or set another `CABLE_PORT`), or
fix the `host` of `CABLE`.

### ⚠️ Upgrading: `url_for` percent-encodes and checks whole values

`url_for` now percent-encodes the path (the placeholder values and the text
of the route around them) and the query string, and a value must match its
placeholder's format as a whole. In the path, every character is encoded
except letters, digits, `-._~`, `/` and `:@!$&'()*+,;=` (the ones a path
allows as they are), so `url_for` gives different URLs for values, or route
text, with a space, `?`, `#`, `%`, `"`, `<`, `>`, `[`, `]`, `{`, `}`, `|`,
`\`, `^`, a backtick or a non-ASCII character. This also applies to URL
templates for JavaScript built with `url_for`: a marker such as
`":signed_id"` stays as written, but one such as `"{id}"` becomes
`%7Bid%7D`; use a marker made of the characters above.

Query values are encoded as a form (`urlencode`), so more characters change
there: a space becomes `+`, and `/`, `:`, `@`, `,`, `[` and `]` are
percent-encoded. `url_for("Auth.login", next="/admin/x")` was
`/login?next=/admin/x` and is now `/login?next=%2Fadmin%2Fx`. The app reads
the value back the same, but a test that asserts an exact URL or a redirect's
`Location` with such a value must be updated.

Six things to change:

- Pass raw values. A value you encoded yourself is encoded again:
  `url_for("Tag.show", tag=quote(name))` gives `/tags/a%2520b` for `"a b"`;
  write `url_for("Tag.show", tag=name)`.
- A value with a `/` now raises `BadRoutePlaceholder`, unless its
  placeholder's format accepts a `/` (`<path>`). It built a broken link
  before: `url_for` for `/posts/:slug` with the slug `"a/b"` gave
  `/posts/a/b`, which doesn't match the route. Now the page that renders the
  link, with `url_for`, `url_is` or `url_startswith`, fails with a 500. If
  your data (slugs, titles, codes) can have a `/`, use a `<path>`
  placeholder, or remove the `/` from the value.
- Any other value that only started with a valid one, such as `"42abc"` for
  an `<int>` placeholder or `"english"` for `<en|es|pt>`, also raises
  `BadRoutePlaceholder` instead of building a URL that doesn't match the
  route. Pass the right value.
- A value that makes a `.` or `..` segment of the path, such as `"."` or
  `".."` for `/files/:name`, or `"a/../b"` for a `<path>` placeholder, also
  raises `BadRoutePlaceholder`. Browsers and HTTP clients remove those
  segments, and the one before a `..`, so `/files/..` opened `/`. If your
  data can be `.` or `..` (file or folder names), pass it in the query
  string, or prefix it. For the same reason, a route no longer matches a
  request whose value for a placeholder is a `.` or `..` segment, which
  only a client that keeps those segments sends (`curl --path-as-is
  /files/..`): the router tries the next routes, and without another
  match the response is a 404. Before, the action got `".."` as the
  param.
- `_anchor` is percent-encoded like the path, keeping `?` as it is:
  `_anchor="a b#c"` gives `#a%20b%23c` (it was `#a b#c`). Pass the anchor
  unencoded; an anchor you encoded yourself (`"a%20b"`) is encoded again
  (`#a%2520b`), and then no longer finds the element with the `id` `a b`.
- With `_full=True`, a value for a host placeholder (`host=":user.app.com"`)
  may have only letters, digits and `-._~` (the unreserved characters of
  RFC 3986); any other character raises `BadRoutePlaceholder`, whatever the
  placeholder's format. Host values are not encoded, so `"evil.com?"` gave
  `http://evil.com?.example.com/...`, a link to `evil.com`. Convert an
  international name to its `xn--` form first
  (`"josé".encode("idna").decode()`); a value with `!`, `$`, `&`, `'`, `(`,
  `)`, `*`, `+`, `,`, `;`, `=`, `%`, `@`, `:` or a space can't be a host
  label.

### ⚠️ Upgrading: `url_is` and `url_startswith` compare paths only

`url_is` and `url_startswith` now compare only the paths, percent-decoded,
and ignore the query string and the `#fragment`. Two things to check in the
templates:

- `url_startswith` is now `True` on every page for a route at `/` (it was
  always `False`). A "Home" link that used it now looks active everywhere;
  use `url_is("Home.index")` for it.
- Query arguments are ignored: `url_is("Photo.index", page=2)` is now `True`
  on `/photos` and on `/photos?page=3`. To mark the current page of a
  pagination, compare the page number with `request.query` instead.

`curr_url` is read as a URL, as in a link, so it is percent-decoded; pass
`quote(path)` to compare with a path you have decoded yourself.

### ⚠️ Upgrading: `TestClient` percent-decodes the path

`TestClient` and `make_test_request` now percent-decode the request path
before routing, as the WSGI server does. A test that requests an encoded path
gets the decoded param: `client.get("/tags/a%20b")` gives `"a b"` (it was
`"a%20b"`), and `client.get("/files/a%2Fb")` gives a 404 for a `/files/:name`
route, as on a server, since the path is `/files/a/b`. Update the asserts to
the decoded value, and use a `<path>` placeholder for a value with a `/`.

### ⚠️ Upgrading: the most specific error handler wins

An error now goes to the handler registered for the closest class in its
hierarchy, not to the first registered handler that matches it. If a
handler for a base class (such as `Exception`) was registered before a
handler for a subclass (such as `NotFound`), the subclass handler was never
called and now it is. If you want the base class handler to take those
errors, remove the subclass handler.

A handler registered for an abstract base class no longer gets the errors of
the classes registered with `ABC.register()` (its virtual subclasses), as an
`except` clause doesn't either. Those errors now go to a handler for one of
their real base classes, or to the default error page. To keep them in that
handler, register it for the concrete classes too, or make them inherit from
the ABC.

### ⚠️ Upgrading: `set_signed_cookie` signs with the salt `"cookie"`

`response.set_signed_cookie()` now signs with the salt `"cookie"` by
default, as `set_cookie(signed=True)` and `request.get_signed_cookie()`
already did. It used `""`, so a cookie set without a salt couldn't be read
back without one. If you worked around it by reading with
`get_signed_cookie(name, salt="")`, the cookies set after the upgrade don't
verify. Add `salt=""` to the `set_signed_cookie()` call too: the cookies
that browsers keep from before the upgrade, signed with `""`, stay valid,
and nothing else changes. (Removing `salt=""` from the read instead also
works for new cookies, but every cookie set before the upgrade then fails to
verify, so its users lose what it kept, such as a "remember me" login.)

### ⚠️ Upgrading: JSON bodies that are not an object, malformed multipart

`request.form` now gets only the members of a JSON object. A JSON body
that is a list of pairs (`[["name", "ada"]]`) or of two-character strings
filled the form before; now it leaves the form empty, as any other JSON
value that is not an object does (other values were a 500). If a client
sends such a body, parse it from `request.body`:
`json.loads(self.request.body)`.

A multipart body that ends before its final boundary is now a
`MultipartError` (400); before, it was parsed without its last field.
Malformed multipart framing is also a `MultipartError` now, where it was
python-multipart's `MultipartParseError` (a 500). An error handler
registered for python-multipart's exception no longer gets these errors;
register it for `MultipartError` instead.

### ⚠️ Upgrading: `request.host` is the `Host` header

`request.host` and `request.port` (and so `host_with_port`, `port_string`
and `port_is_default`) now come from the `Host` header, as PEP 3333
rebuilds the URL, and the host is lowercased. Only a request without a
`Host` header (HTTP/1.0), or with an empty one, gets the address the server
listens on. Before, they were always that address (`SERVER_NAME`), which
under `proper run` is `0.0.0.0` or the Unix socket: routes with a `host`
answered 404, and `OriginProtection` never matched the `Origin` with the
host (its step 5).

- Behind a proxy, make it pass the client's `Host` through: nginx needs
  `proxy_set_header Host $host;` (in the deployment guide's example), or it
  sends the address in `proxy_pass` (`127.0.0.1:2300`), and the routes for
  a host answer 404.
- An invalid `Host` header (`example.com/x`, a space, `user@example.com`,
  brackets around something that is not an IPv6 address: `[abc]`,
  `[127.0.0.1]`) is now a `400 Bad Request`. It was ignored. So is a
  request with more than one `Host` line, as RFC 9112 §3.2 requires, even
  when the lines are the same: Granian joins them with a comma
  (`a.com,b.com`), so a `Host` with a comma is refused, and a `Request`
  built with repeated `host` pairs gets the same 400.
- `OriginProtection` step 6 (both the `Origin` and the host on the local
  network) now needs the `Host` to be a local address. Before, the host was
  the bind address (`0.0.0.0`, which counts as local), so any `Origin` on
  the local network passed, also for a request to your public host name.
- `make_test_request(server=...)` and `Request(server=...)` no longer
  override the `Host` header: a test that set both gets the header's host.
- `host_with_port` gives an IPv6 host in brackets, as in the `Host`
  header: `[2606:4700::1]:8080`, not `2606:4700::1:8080`. Code that splits
  it at the last `:` or adds the brackets itself must not do so any more.
- `make_test_request` lowercases the header names, as the server does:
  a test that passed `headers={"Host": ...}` or `{"X-Api-Key": ...}`, which
  the request didn't see before, now has them. With an IPv6 URL,
  `request.server` is the address without brackets (`("::1", 8080)`, it
  was `("[::1]", 8080)`), as Granian gives it.

The client chooses the `Host` header. Proper uses it only to pick the route
and to compare it with `Origin`: `url_for(..., _full=True)`, the
password-reset email and the storage URLs use `PROTOCOL` and `HOST` from the
config, or the route's own host, so a forged `Host` can't put another host
in a link sent to someone else. Do the same in your code: build absolute
URLs that leave the request with `url_for(..., _full=True)`, not from
`request.host`. `X-Forwarded-Host` and `Forwarded: host=` are not read.

### ⚠️ Upgrading: the auth `Session` stores any IP address

The auth addon's `Session.ip_address` was a `pw.IPField`, which stores IPv4
addresses only: signing in was a 500 (`OSError`) for a visitor with an IPv6
address, for an IPv4 visitor of Granian listening on `::`
(`::ffff:203.0.113.5`), and for a `remote_ip` that is not an address
(an identifier a proxy wrote, such as `unknown` or `_hidden`, or `""`
without one). New apps get
`pw.CharField(max_length=255, null=True)`, and `create_for_user` stores
`remote_ip` cut to 255 characters, or `None` if it is empty. `remote_ip`
has no length limit (a proxy can write any identifier), but an address is
at most 45 characters.

An app made before has the old field, and **must run the migration below
when it upgrades**. Without it, the app still runs and IPv4 visitors sign
in as before, but signing in is still a 500 (`OSError`) for any
`remote_ip` that `socket.inet_aton()` refuses, which includes an IPv6
address, an IPv4 address of Granian listening on `::`
(`::ffff:203.0.113.5`), an identifier a proxy wrote instead of an address
(`unknown`, `_hidden`), and `""`. Proper doesn't work around the
old field. Change the field in `models/session.py`:

```python {title="models/session.py"}
ip_address = pw.CharField(max_length=255, null=True)
```

and in `create_for_user`, `ip_address=ip_address[:255] if ip_address else
None`. Then run `proper db create session_ip_address_text`. It writes the
`change_fields` call; add the conversion of the stored numbers (an
`IPField` keeps each address as a number), and replace the rollback, which
Postgres can't run as written (it can't change a text column into a
number without a `USING` clause):

```python {title="db/main/NNN_session_ip_address_text.py"}
import ipaddress

import peewee as pw
from peewee_migrate import Migrator


def ip_numbers_to_text(migrator):
    """`IPField` stored each IPv4 address as a number."""
    Session = migrator.orm["session"]
    for session in Session.select().where(Session.ip_address.is_null(False)):
        session.ip_address = str(ipaddress.IPv4Address(int(session.ip_address)))
        session.save(only=[Session.ip_address])


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.change_fields("session", ip_address=pw.CharField(max_length=255, null=True))
    migrator.run(ip_numbers_to_text, migrator)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    # `IPField` takes only IPv4 addresses: the stored addresses are dropped.
    migrator.remove_fields("session", "ip_address")
    migrator.add_fields("session", ip_address=pw.IPField(null=True))
```

and run `proper db migrate`.

### ⚠️ Upgrading: forwarding headers count only from `TRUSTED_PROXIES`

`request.remote_ip` and `request.protocol` now read the `X-Forwarded-For`,
`Forwarded`, `X-Real-IP` and `X-Forwarded-Proto` headers only when the
request comes from one of the reverse proxies in the new `TRUSTED_PROXIES`
setting, or from a peer without an address (Granian or gunicorn on a Unix
socket, which only a process on the same machine can reach). From any other
address they are ignored, and `remote_ip` is the address the request came
from.
`request.protocol` decides `request.is_secure`, `default_port`,
`port_is_default`, `port_string` and `host_with_port`, and whether the
session and auth cookies are `Secure`: behind a proxy that is not in the
list, they lose the `Secure` flag without any error.

The default is the loopback, private and link-local networks
(`127.0.0.0/8`, `::1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`,
`169.254.0.0/16`, `fc00::/7`, `fe80::/10`). An app whose only proxy is on
the same machine or the same private network needs no change. Every proxy
in the chain must be in the list, also the ones that never connect to the
app: if your proxy connects to the app from another address (a load
balancer with a public IP), or a CDN or public load balancer sits in front
of your local nginx (Cloudflare or CloudFront in front of nginx, CloudFront
in front of an ALB), add their addresses in `config/main.py`, along with
the default ranges you still need, since the list replaces them:

```python {title="config/main.py"}
TRUSTED_PROXIES = ["127.0.0.1", "203.0.113.0/24"]
```

Each item is an IP address or network, as a string or an `ipaddress`
object; anything else (an int, bytes, a host name) stops the app with a
`ConfigError`.

The default trusts every loopback, private and link-local address, so a
client that reaches the app, or the first proxy, from one of them counts as
a proxy: another machine on the same LAN or VPC, a container on the same
host, or every visitor behind a load balancer that replaces their address
with its own private one (SNAT). Such a client can choose its `remote_ip`
(`X-Forwarded-For`, `X-Real-IP`) and make the request secure
(`X-Forwarded-Proto: https`). If clients can connect from those networks,
list only your proxies' addresses. And the proxy must overwrite
`X-Forwarded-Proto` with the scheme it got the request on (nginx:
`proxy_set_header X-Forwarded-Proto $scheme;`), not append to it or pass
the client's through: the app uses the header's whole value.

Without the CDN's ranges, `X-Forwarded-For` arrives as
`<visitor>, <CDN edge>`, and `remote_ip` is the CDN edge's address for every
visitor (it was the visitor's, the leftmost). The default `rate_limit` then
puts every visitor behind one edge in one bucket, so they all get 429s
together, and the auth sessions record the CDN's address.

Four more changes in how `remote_ip` reads the headers:

- `X-Forwarded-For` and `Forwarded` are read from the right, skipping the
  trusted proxies, so it is the address of the first hop that is not one.
  It was the leftmost address, which the client writes itself. If every
  address is a trusted proxy, it is still the leftmost one.
- `X-Forwarded-For` comes before `Forwarded` (it was the other way round),
  because nearly every proxy writes `X-Forwarded-For` and passes a client's
  `Forwarded` header through untouched. A proxy passes the forwarding
  headers it doesn't write as the client sent them: behind a proxy that
  writes only `Forwarded`, make it remove the client's `X-Forwarded-For`;
  behind one that writes only `X-Real-IP`, make it remove the client's
  `X-Forwarded-For` and `Forwarded`.
- An `X-Forwarded-For` or `Forwarded` address is returned without a port
  or brackets that a proxy added (`203.0.113.5:51234` gives `203.0.113.5`,
  `"[2001:db8::7]:4711"` gives `2001:db8::7`), and an IPv4-mapped address
  as IPv4 (`::ffff:203.0.113.5` gives `203.0.113.5`). With the port, the
  default `rate_limit` counted each connection of a client on its own.
  `Forwarded` is split into its elements at the commas outside quoted
  strings, from the right, where the trusted proxies' elements are: a comma
  in a quoted value of a proxy's element (`host="a,b"`) doesn't split it,
  and a quoted string that the client leaves open can't take in the element
  a trusted proxy appends.
- A forwarding header sent in several lines is read as one list, the lines
  joined in order (RFC 9110 §5.3). Only the last line was read. (Granian
  already joins the lines into one value; this is for a `Request` built
  with repeated headers, as in tests.)

Make the proxy drop the request headers with an underscore in the name,
such as `X_Forwarded_For`. The WSGI server gives the app `X-Forwarded-For`
and `X_Forwarded_For` under the same name, so the app can't tell the
client's header from the proxy's, and Granian can keep the client's value.
nginx drops these headers unless `underscores_in_headers` is on or
`ignore_invalid_headers` is off; a proxy built on Go's
`httputil.ReverseProxy` passes them through.

In tests, `TestClient` requests now come from the address
`client.remote_ip` (`127.0.0.1`, a trusted proxy), so an `X-Forwarded-For`
header you send in a test is used. Before, the client's own `Forwarded`
header won over it. A test that sets `client.remote_ip` to a public address
now gets the forwarding headers ignored: an `X-Forwarded-Proto: https` sent
to test `Secure` cookies no longer makes the request secure. Keep the
default address for those tests. `make_test_request()` without `client=`,
and `Request(...)` without `client`, have no peer address, which counts as
trusted, so their forwarding headers are still used, by the rules above:
`X-Forwarded-For: 1.2.3.4, 5.6.7.8` now gives `5.6.7.8` (it gave
`1.2.3.4`), and it wins over `Forwarded`. A WebSocket handshake without a
peer address, which only the in-memory test server's `connect()` without
details gives (wse always sends one), does not count as trusted: its
`X-Forwarded-For` is dropped, and `remote_ip` is `""`.

### ⚠️ Upgrading: conditional requests follow RFC 9110 more closely

`response.is_fresh()`, and so the automatic `304 Not Modified` after an
action and the return value of `fresh_when()`, now follow these rules of
RFC 9110:

- A response can be fresh only for a `GET` or `HEAD` request and with a
  2xx status. Before, a `POST` with a matching `If-None-Match`, or an
  action that set a 404 or a redirect, could get its status replaced by
  304 and lose its body. Now that response is sent in full, and
  `fresh_when()` and `is_fresh()` return `False` for it when the status is
  already set (`fresh_when()` can't know a status the action sets after
  calling it, but the 304 is decided with the final status). If an action
  used their return value on another method or status, it must not
  count on `True` there any more.
- `If-Modified-Since` is ignored when the request has an
  `If-None-Match`. Before, an ETag that didn't match could still get a 304
  from the date. Static files have no ETag, so a request for one that
  carries an `If-None-Match` other than `*` now always gets a 200. If a
  proxy or CDN in front of the app adds its own `If-None-Match` to the
  requests it revalidates, make it send only `If-Modified-Since` for
  static files, or they lose their 304s.
- `If-None-Match` uses the weak comparison (`W/"x"` matches `"x"`), and
  `If-None-Match: *` matches any 2xx response to a `GET` or `HEAD`, with or
  without an ETag, static files included (RFC 9110 §13.1.2: the resource
  exists). Before, only the exact string matched, so more requests now get
  a 304. An action that answers 2xx to a `GET` with `If-None-Match: *` now
  sends a 304 without a body even if it never calls `fresh_when()`.

One RFC 9110 rule is not applied: a request with another method whose
`If-None-Match` matches gets the response as it is, not a
`412 Precondition Failed`.

A response with the status 304 now always goes out without a body, also
when the action sets the status itself: the body is emptied, whatever the
action returned, and no template is rendered. Before, the body was emptied
only when the request's headers made the response fresh.

### ⚠️ Upgrading: dates in headers must be in an RFC 9110 form

`request.date` and `request.if_modified_since` now read only the three date
forms of RFC 9110 §5.6.7, all in UTC:

- `Sun, 06 Nov 1994 08:49:37 GMT` (IMF-fixdate, what `Last-Modified` has);
- `Sunday, 06-Nov-94 08:49:37 GMT` (obsolete RFC 850);
- `Sun Nov  6 08:49:37 1994` (ANSI C's `asctime()`, with two spaces before a
  one-digit day, or `Nov 06`).

Any other date is ignored (`None`), as an invalid date already was. Before,
python-dateutil read almost anything: ISO 8601 (`1994-11-06T08:49:37Z`),
numeric offsets (`+0200`), `UTC` instead of `GMT`, a one-digit day in
IMF-fixdate or RFC 850 (`Sun, 6 Nov 1994 08:49:37 GMT`), an asctime
one-digit day with one space before it instead of two
(`Sun Nov 6 08:49:37 1994`), lowercase names, extra spaces. Those are now
ignored, so an `If-Modified-Since` in such a form gets the full response
instead of a 304. Browsers and HTTP clients send the date of
`Last-Modified` back as it came, so nothing changes for them; update a
client or a test that builds its own dates in another form.

The day name is not checked against the date. In the RFC 850 form, a
two-digit year is taken in the next century, this one or the one before:
the latest of those three years that has the date and makes it, to the
second, not more than 50 years in the future, as RFC 9110 says. When none
of them does, the header is ignored (`None`). So the year can depend on
the day: on 8 October 2026 at 12:00 UTC, `08-Oct-76 12:00:00` is 2076, but
`08-Oct-76 12:00:01` and `09-Oct-76` are 1976. Throughout 2026, `77` is
1977; throughout 2051, `00` is 2100, but `29-Feb-00` is 2000, because 2100
has no 29 February. Second 60 is read as second 59 at any time of day
(`08:49:60` as `08:49:59`, not only `23:59:60`): the grammar of RFC 9110
allows seconds from 00 to 60.

### ⚠️ Upgrading: Proper no longer installs python-dateutil

Proper read the dates in headers with python-dateutil; it now reads them
itself (see above), and python-dateutil is no longer one of its
dependencies. An app that imports `dateutil` and got it only because Proper
installed it must add it to its own dependencies:

```bash
uv add python-dateutil
```

### ⚠️ Upgrading: `Accept` weights outside 0 to 1, and `Q`

In `Accept`, `Accept-Encoding` and `Accept-Language`, a `q` that is not a
number from 0 to 1 now counts as 1, as if it were not there. Before, `q=2`
put the value first and `q=-1` put it last (and `q=abc` was a 500). The
parameter names are now case-insensitive, as RFC 9110 says, so `Q=0.1` is
a weight: `text/html;Q=0.1, application/json` now prefers JSON (before,
`Q` was ignored and HTML came first). `request.accept`,
`request.accept_language` and the template that an action renders for a
format follow this order. Nothing to change unless a client (or a test)
counted on `q` over 1 or on an uppercase `Q` being ignored.

### ⚠️ Upgrading: bodies that can't be read are client errors, chunked bodies are read

Request bodies that the app can't read are now 4xx errors, raised before
the action, where they were 500s:

- Bytes that are not valid in the charset of a urlencoded or JSON body:
  `BadRequest` (400).
- An unknown charset (`charset=nope`, or a name that Python can't look up,
  such as one with a NUL), or a charset that can't decode the
  percent-escapes of a urlencoded body (`charset=idna`):
  `UnsupportedMediaType` (415).
- JSON with an integer of more than 4300 digits, or with arrays and
  objects nested deeper than the stack allows: `MultipartError` (400), as
  malformed JSON already was.
- Malformed multipart framing: `MultipartError` (400), as described above.

They go to your error handlers for those classes (or for `BadRequest`), not
to a handler for `UnicodeDecodeError`, `LookupError`, `ValueError` or
`RecursionError`, and the client gets the 4xx page. If you had such a
handler, register it for `BadRequest` or `UnsupportedMediaType` instead.

Chunked bodies (`Transfer-Encoding: chunked`) and HTTP/2 bodies without
`Content-Length` are now read from servers that set
`wsgi.input_terminated` (Granian, gunicorn and waitress do), up to
`MAX_CONTENT_LENGTH`; one over it is a 413. Before, such a body was
ignored and the action got an empty `request.form` and `request.body`.
Check that:

- An action that accepted these requests and ignored the empty body now
  gets the body, and validates it.
- `request.content_length` stays `0` for such a body. Code that reads
  `content_length` to know whether there is a body should check
  `request.body` instead.
- With `MAX_CONTENT_LENGTH = 0` (no limit), the whole body is read into
  memory; set a limit if the app gets chunked uploads.

### ⚠️ Upgrading: `app.loads()` returns `None` for tokens it can't decode

`app.loads()` now returns `None`, as for a bad signature, for a token whose
signature is valid but whose payload it can't decode (not valid base64,
zlib, UTF-8 or JSON) or whose timestamp is after the year 9999. It raised
`itsdangerous.BadPayload`, `ValueError` or `OverflowError`. Code that
caught those exceptions around `loads()` must check for `None` instead; the
`except` clauses no longer run. Signed cookies and the session read such a
token as missing, where they were a 500.

### ⚠️ Upgrading: a host longer than 255 characters matches no host route

A request whose host (`request.host`, without the port) is longer than 255
characters now matches no route with a `host`, whatever its pattern; the
routes without a `host` still match it. A DNS name has at most 253
characters, so no browser sends such a host. The limit shortens the text
that `re` reads for a host pattern with a custom format, but does not bound
that time (see "Fixed").

### ⚠️ Upgrading: `RouteTemplate` is removed

`proper.router.RouteTemplate`, the `string.Template` with `:name`
placeholders that `url_for` used to build URLs, is gone; nothing in Proper
uses it now. Importing it, from `proper.router` or `proper.router.route`,
raises `ImportError`. To build the URL of a route, use `url_for`, which
follows the placeholder rules of the routes (`RouteTemplate` didn't). Code
that used the class for its own strings can define it, as it was:

```python
from string import Template

class RouteTemplate(Template):
    delimiter = ":"
```

### Removed

- `proper.router.RouteTemplate` (see "Upgrading" above).
- The dependency on python-dateutil (see "Upgrading" above).
- `RedisCable`. Several machines are now the `cluster` option of `Cable`,
  on wse's own mesh (see Added), which also carries presence and recovery
  between machines, something Redis pub/sub couldn't.
- The in-process cable and its WebSocket process: `proper.core.app_ws`, and
  the second, RSGI, process that `proper run` started on `CABLE_PORT`.
  `CABLE = {}` (the default) is now a `Cable` that serves no WebSockets: a
  `broadcast()` reaches no one. `CABLE_PORT` with an empty `CABLE` is a
  `ConfigError`.
- RSGI: `App.__rsgi__`, `App.startup()` and `App.shutdown()` (`app.lower()`
  stays), the app's own thread pool, and `Cable.start()`/`Cable.stop()`
  (`Cable` has `start_server()`/`stop_server()`, which `proper run`
  calls).
- The settings `INTERFACE`, `THREAD_WAIT_WARNING`, `LOOP_STALL_WARNING` and
  `CABLE_MAX_PENDING` (`CABLE_MAX_PENDING_BYTES` and `CABLE_STALL_TIMEOUT`
  stay).
- From `proper.test_client`: `make_test_scope`, `make_test_ws_scope`,
  `HttpProtocolStub` and `WsProtocolStub`. `client.websocket()` always runs
  the app's `Cable` from memory, and no longer takes a path, which the
  in-memory server doesn't use; with a cable that serves no WebSockets,
  `connect()` raises `RuntimeError`.

### Added

- `TRUSTED_PROXIES`: the IP addresses or networks (CIDR) of the reverse
  proxies in front of the app, whose forwarding headers are used. A value
  that is not a list of addresses or networks is a `ConfigError`. The app
  keeps it in `app.config.TRUSTED_PROXIES` as a tuple of `ipaddress`
  networks; a list of strings assigned there later is also accepted.
- `app.cable.health()`: whether this process serves the WebSockets, its
  connections, users and streams, and what wse reports (`health_snapshot()`),
  for a health endpoint.
- Prometheus: the process that serves the WebSockets answers `GET /metrics`
  on the loopback port `CABLE_PORT + 1` with wse's metrics and the cable's
  (`proper_cable_streams`, `proper_cable_users`); `app.cable.metrics()` is
  the same text.
- Several machines: `CABLE["cluster"]` (`port`, `peers` or `seeds` and
  `addr`, `tls`) joins the cables in wse's TCP mesh. A `broadcast()` reaches
  every machine's subscribers, `disconnect()` closes a user's connections
  everywhere, presence is one list, and recovery knows the other machines'
  broadcasts: `cable.js` keeps a position per stream and epoch and sends
  them all (`positions` is a list per stream now; the old form is still
  accepted). `app.cable.cluster_info()` lists the peers. Needs proper-wse
  >= 2.7.0 (`subscribe_node`).
- Presence: `Channel.track(stream, data, key=...)` lists the connection
  among those present in a stream, under the user's id (three tabs count
  once), a random key for anonymous connections, or a key the server
  chooses; `untrack()` and `update_presence()`; `app.cable.presence(stream)`
  and `presence_stats(stream)`. The stream's subscribers get
  `presence_join`, `presence_leave` and `presence_update`, the
  confirmation lists who is there, and `cable.js` has a
  `presence(users, change)` callback. `Cable(presence=False)` turns it
  off. Needs proper-wse >= 2.7.0.
- A channel's `self.request` is now the whole handshake: its path and query
  string (`request.query`), its `Authorization` and `X-Forwarded-For`
  headers, and the client's address (`request.remote_ip`), besides the
  cookies. And `Channel.find_session()` is the hook that finds the
  connection's session, from the signed cookie by default; override it to
  accept a token from a client without cookies, such as a mobile app. Needs
  proper-wse >= 2.7.0 (`handshake_details`). `client.websocket(path)` takes
  the handshake's path, with a query string, and sends the client's
  `authorization` header.
- Missed broadcasts are recovered. `Cable` keeps the last broadcasts of
  each stream (`recovery=True`; wse's `recovery_buffer_size`, 128 per stream,
  `recovery_ttl`, 300 seconds, and `recovery_memory_budget`, 256 MB, size the
  buffers), and a `cable.js` that reconnects, or notices a hole in a stream,
  asks for the ones it missed; they come through `received()`, in order,
  with no duplicates. `connected()` now gets `{reconnected, recovered}`;
  `recovered === false` (the server restarted, another machine, too many
  missed) is the moment to load the state again, and
  `<turbo-stream-channel>` dispatches `turbo-stream-channel:gap` then. On the
  wire, broadcasts carry wse's `tp`/`e`/`o` stamp, `subscribe` may carry
  `positions`, and `confirm_subscription` has `positions` and `recovered`.
  `WebSocketTestSession.subscribe()` takes `positions=`.
- Replies to actions. `perform()` in `cable.js` returns a promise that
  resolves with what the action returned, and rejects with the data of an
  `ActionError` the action raised (`raise ActionError("too_long", max=500)`
  → `{reason: "too_long", max: 500}`), with `{reason: "error"}` when it
  raised anything else (logged, as before, but the client no longer waits
  for nothing), with the reason when there was nothing to run, and with
  `{reason: "timeout"}` after 10 seconds. On the wire, a `message` with an
  `id` gets a `reply` frame. `WebSocketTestSession.perform()` returns it.
- `cable.js` keeps the `perform()` calls made while the connection is down
  and sends them once it, and its subscriptions, are back. It used to drop
  them. Apps created before need the new `assets/js/cable.js`, from Proper's
  `_blueprints/addon_channels/assets/js/cable.js`.
- `proper.db.prepare(query)` and `proper.db.Param`: prepared queries, compiled
  to SQL once and executed many times with new values, on the released Peewee.

### Fixed

- `request.host` was the address the server listens on (`0.0.0.0` under
  `proper run`), never the `Host` header, so routes with a `host` answered
  404 and `OriginProtection` never matched the `Origin` with the host. It
  is now the `Host` header, and an invalid one is a 400.
- A request to a local host matches only the routes without a `host`, but
  the host was compared with five exact strings (`localhost`, `0.0.0.0`,
  `127.0.0.1`, `::`, `::1`), so `127.0.0.1.`, `127.000.000.001`, `127.1`,
  `localhost.`, `[0:0:0:0:0:0:0:1]` or `[::ffff:127.0.0.1]` matched the
  routes with a `host` (`:sub<.+>` takes any host). Now every spelling of
  those addresses counts as local, with percent-escapes decoded:
  `localhost` and any IPv4 address in 127.0.0.0/8 or 0.0.0.0, read as
  browsers read the host of a URL (decimal, octal, hex, one to four
  parts), with or without one trailing dot, or `::1` and `::` in any IPv6
  form, also mapped from IPv4. `proper.pipeline.is_local_host` tells it.
- `request.host_with_port` didn't put an IPv6 address back in brackets:
  `Host: [2606:4700::1]:8080` gave `2606:4700::1:8080`, which never equals
  the `Origin`, so `OriginProtection` refused a same-origin `POST` to an
  IPv6 address unless the browser sent `Sec-Fetch-Site`. It now gives
  `[2606:4700::1]:8080`, also for the server's address without a `Host`
  header.
- `make_test_request` passed the header names as given, and `Request`
  reads lowercase names only, so `headers={"Host": "api.example.com"}` gave
  `request.host == "example.com"`, and any other name with a capital letter
  was not seen. The names are now lowercased, as `TestClient` and the
  server give them; a name given more than once stays repeated, in order.
  A URL with an IPv6 address and no port (`http://[::1]/`) raised
  `ValueError`, and with a port `request.server` kept the brackets
  (`("[::1]", 8080)`); it is now `("::1", 8080)`, as Granian gives it.
- An `Origin` header that `urlparse` refuses (`http://[abc]`,
  `http://[::1`, `http://example.com]`) made every `POST` to a controller
  with `OriginProtection`, `AppController` included, a 500. Such an origin
  now matches no host, so the request is refused with a 403 unless
  `Sec-Fetch-Site` allows it. `proper.channels.origin_allowed` raised
  `ValueError` for the same origins, and for a handshake `Host` such as
  `[abc]`; it now returns `False`.
- The `RateLimiting` docstring keyed a signup limit on `request.host`, the
  client's `Host` header, so a client following it could pick its own limit.
  The example now keys on the e-mail domain of the form, next to a limit by
  IP, and the docs say that an identity taken from the request is chosen by
  the client.
- Signing in with the auth addon was a 500 for IPv6 visitors, for IPv4
  visitors of a server listening on `::`, and when `remote_ip` was not an
  address: `Session.ip_address` was an `IPField`, which takes IPv4 only.
  It is now text in new apps; apps made before need the migration in
  "Upgrading" above.
- Any client could set `request.remote_ip` with a `Forwarded`,
  `X-Forwarded-For` or `X-Real-IP` header, and make `request.is_secure`
  true (and so the session and auth cookies `Secure`) with
  `X-Forwarded-Proto`: the headers were used whoever sent them. Now they
  are used only from the `TRUSTED_PROXIES` or from a peer without an
  address (a Unix socket), and the address lists are read from the right.
- The error handler lookup used the first registered handler whose class
  matched, so a handler for `Exception` registered before one for
  `NotFound` also took the 404s. Now the most specific handler wins, as
  with `except` clauses: the one for the closest class in the error's
  hierarchy, whatever the registration order. A handler registered for an
  ABC no longer matches the ABC's virtual subclasses (`ABC.register`), as
  an `except` clause doesn't either.
- `url_for` didn't percent-encode: a value with a space, `?`, `#`, `&` or
  `%` gave a broken URL, or a query string with other parameters. Path values
  and query keys and values are now encoded. A query value that is not a
  string is encoded from its `str()`: `c=[1, 2]` gives `c=%5B1%2C+2%5D`
  (it was `c=[1, 2]`), which the app reads back as the same `"[1, 2]"`.
- `url_for` accepted a value that only started with a valid one (`"42abc"`
  for `<int>`); now the whole value must match.
- Matching a route whose pattern has several placeholders that can match
  the same characters took time that grows as a power of the length of the
  path or host, which the client chooses: Python's `re` tries every way to
  split the text between the placeholders before it gives up. A `Host` of
  2 000 dots and an `x` against `:a.:b.:c.example.com` took 12.8 s, and a
  path of 2 001 characters against `/x/:a-:b-:c.html` 10.8 s, each
  blocking a worker. Such patterns are now matched in time linear in the
  length (a path of 64 001 characters: 0.05 s), with the same results as
  `re`, by a matcher that marks, from the right, where the rest of the
  pattern can still match, and then gives each placeholder the first
  choice `re` would take. It is used for the built-in formats and for
  custom formats that are a run of one class of characters (`[a-z]+`,
  `\d{4}`) or literal texts separated by `|`. `re` is still used where it is
  fast: on short subjects, and for patterns on which it can't backtrack much
  (no placeholder but the last can end in more than one place, as in
  `/posts/:id/edit`). A length limit alone would not have been enough: paths
  have no natural limit, and with four placeholders `re` took 1.6 s for a
  host of 255 characters. A route with any other custom format is matched
  with `re` as before, and the 255-character limit on hosts (see
  "Upgrading") does not bound its time, which depends on the format: `re` is
  slow when two placeholders can match the same characters, or when a format
  can match the same text in many ways. `:sub<(?:[a-z0-9]+-?)+>.example.com`
  took 5.8 s for a host of 27 characters; with `[a-z0-9]+(?:-[a-z0-9]+)*`,
  which matches a text in only one way, it takes under 1 ms for 255.
- `url_for(..., _full=True)` put the value of a host placeholder into the
  URL as it was: with `host=":sub.example.com"`, `sub="evil.com?"` gave
  `http://evil.com?.example.com/h/1`, a link to `evil.com`, and `@`, `/`
  (with a format that accepts it), a space, CR or LF changed the URL too. A
  host value with a character other than letters, digits and `-._~` now
  raises `BadRoutePlaceholder`.
- `url_for` copied the text of the route as written, so a route such as
  `/über/:id` or `/my files/:id` gave an invalid URL, and a non-latin-1
  character in it broke the `Location` header of a redirect. The text is now
  percent-encoded as the values are: `/%C3%BCber/42`.
- `url_for` (and the host for `_full=True`) read the route with
  `string.Template` rules, not the placeholder rules used for matching: `:ID`
  in a path raised `KeyError`, `10:30` or a host with a port
  (`localhost:5000`) raised `ValueError`, `/:a<int>bc` raised `KeyError`,
  and `/a::b` lost a `:`. The text that is not a placeholder is now copied
  as written. `Route` no longer uses `RouteTemplate`, which is removed
  (see "Removed").
- `url_for` copied `_anchor` as it was: `_anchor="a b#c"` gave
  `/photos#a b#c`. It is now percent-encoded with the characters RFC 3986
  allows in a fragment kept: `/photos#a%20b%23c`.
- `url_for` built URLs with a `.` or `..` segment from values such as
  `".."` (`/files/..`), which browsers and HTTP clients turn into another
  URL (`/`). Such a value now raises `BadRoutePlaceholder`.
- `If-None-Match: *` matched only a response with an ETag, so a `GET` for a
  page or a static file without one got a 200. It now matches any 2xx
  response to a `GET` or `HEAD` (RFC 9110 §13.1.2), which gets a 304.
- `url_is` and `url_startswith` didn't ignore the query string and the
  `#fragment` of `curr_url`, contrary to their docstrings, and
  `url_startswith` was always `False` for a route at `/`. They now compare
  the paths only, percent-decoded, and every path starts with `/`.
- `TestClient` and `make_test_request` didn't percent-decode the path, as
  the server does: a test that requested `/tags/a%20b` got the param
  `a%20b`, where the app running on a server gets `a b`.
- `response.set_signed_cookie()` signed with the salt `""` and
  `request.get_signed_cookie()` read with `"cookie"`, so a signed cookie set
  and read with the default salts never verified. Both use `"cookie"` now.
- `app.loads()` raised instead of returning `None` for a token with a valid
  signature that it couldn't decode: a payload that isn't valid base64,
  zlib, UTF-8 or JSON (`itsdangerous.BadPayload`), or a timestamp after year
  9999 (`ValueError` or `OverflowError`). Reading such a cookie with
  `get_signed_cookie()`, or as the session, was a 500.
- `app.loads(token, timed=False)` accepted some timed tokens made with the
  same salt, so a token meant to expire could be read forever where the app
  reads untimed tokens. A timed token is `payload.timestamp.signature`, and
  its signature also covers `payload.timestamp`; when the payload was
  compressed and its base64 text, after the leading `.`, had a length of 2
  modulo 4, `payload.timestamp` decoded to the zlib data with the
  timestamp's bytes after it, which zlib ignores. An untimed load now
  refuses a payload with a `.` after its first character, which no untimed
  token has. Untimed tokens made before still load.
- A session cookie whose signed value was not a JSON object (a string, a
  number, `true`) was a 500, and a list of pairs became a session. Any value
  that is not an object is now no session, as a bad signature is.
- A malformed parameter in `Accept`, `Accept-Encoding` or `Accept-Language`
  was a 500: one without a value (`text/html;level`), an empty one
  (`text/html;`), or a `q` that is not a number (`q=abc`). Such a parameter
  is now ignored; a `q` that is not a number from 0 to 1 counts as 1.
- The parameter names of `Accept`, `Accept-Encoding` and `Accept-Language`
  were case-sensitive, so `text/html;Q=0.1` had the weight 1. They are
  now case-insensitive (RFC 9110 §5.6.6).
- The media type of the request's `Content-Type` was case-sensitive when it
  had parameters: a body sent as `Multipart/Form-Data; boundary=x` or
  `Application/JSON; charset=utf-8` was not parsed. The media type is now
  lowercased, as RFC 9110 says it is case-insensitive. (The parameter names
  were already case-insensitive.)
- A JSON body that was not an object (`[1, 2]`, `"x"`, `3`, `true`) was a
  500. It now leaves `request.form` empty, and the body is in
  `request.body`.
- A urlencoded or JSON body with bytes that are not valid in its charset was
  a 500; it is now a `BadRequest` (400). An unknown charset
  (`charset=nope`) was a 500; it is now an `UnsupportedMediaType` (415).
  So is a charset name with a NUL, which RFC 2231 decoding gives for
  `charset*=utf-8''utf-8%00`; in a multipart body such a charset was a 500
  too, and is now read as Latin-1, as other unknown charsets are. A
  urlencoded body with a percent-escape and `charset=idna` was a 500 too
  (the `idna` codec has no `replace` error handler, which decoding the
  escapes uses); it is now a 415.
- A JSON body that `json.loads()` refuses with something other than a
  `JSONDecodeError` was a 500: an integer with more than 4300 digits
  (`ValueError`), or about 100,000 nested arrays (`RecursionError`). Both
  are now a `MultipartError` (400), as invalid JSON is.
- A malformed multipart body (no boundary line at the start, a header line
  without a colon) was a 500 with python-multipart's own exception; it is now
  a `MultipartError` (400).
- A file or a `last_modified` with a fraction of a second (as most file
  modification times have) never got a `304 Not Modified` from
  `If-Modified-Since`: the header sent to the client has whole seconds, and
  the date it sent back was compared with the full time. They are now
  compared in whole seconds, so unchanged static files get their 304.
- A `Date` or `If-Modified-Since` header that was not a valid date
  (`If-Modified-Since: garbage`) was a 500 in every action that used
  `fresh_when()` and for static files. It is now ignored (`None`), as RFC
  9110 says. A date with a time zone offset (`+0200`) was read as if it were
  UTC; it is now ignored, like every date that is not in one of the forms
  of RFC 9110 (see "Upgrading" above).
- A request body without `Content-Length` was ignored: a chunked
  (`Transfer-Encoding: chunked`) body in HTTP/1.1, or a body sent without
  the header in HTTP/2, left `request.form` and `request.body` empty. It is
  now read, up to `MAX_CONTENT_LENGTH`, and refused with a 413 as soon as
  it goes over it. It is read only from a server that sets
  `wsgi.input_terminated` (Granian, what `proper run` uses, does), because
  PEP 3333 doesn't promise that `wsgi.input` ends where the body does;
  from other servers such a body is still ignored, as in Werkzeug.
  `request.content_length` stays `0` for such a body. With
  `MAX_CONTENT_LENGTH = 0` (no limit), the whole body is read into memory;
  set a limit if the app gets chunked uploads.
- A `subscribed()` that raised an exception after `stream_from()` left the
  connection receiving the broadcasts of that stream, without a subscription,
  and the client waiting for an answer. The streams are now stopped and the
  client gets a `reject_subscription` with `"reason": "error"`.
- A channel registered under another name (`@router.channel("chat")`) sent
  its `send()` messages with the class name, so `cable.js` couldn't find the
  subscription and dropped them. `channel_name` is now the name the client
  subscribed with.
- wse closed every connection that sent it nothing for a minute, so a page
  that only listened reconnected every minute or so, losing the broadcasts
  sent meanwhile. `cable.js` now answers wse's pings. Apps created before
  need the new `assets/js/cable.js`: copy it from Proper's
  `_blueprints/addon_channels/assets/js/cable.js`.
- The channels addon requires proper-wse >= 2.6.2. In older versions, closing
  a connection that had gone silent (a laptop that went to sleep) stopped the
  server's pings and checks for every connection, `unsubscribed()` never ran
  for it, and the server didn't stop. Upgrade with
  `uv add "proper-wse>=2.6.2"`.
- A client could call a channel's `find_user()` as an action. It is now
  refused, like the other channel internals.
- `Cable`: what a channel set on `current` in one command (such as
  `current.auth_session` in `subscribed()`) was still there for the next
  command run on the same worker thread, from any connection. Each command
  now runs in a context of its own.
- `Cable.start_server()` (what `proper run` calls) sometimes left a cable
  that never answered its clients: wse binds `CABLE_PORT` after its
  `start()` returns, and the thread that hands wse's events to the
  channels stopped at once if it looked before then. The connections were
  accepted, and their `subscribe` commands never confirmed. It happened in
  about 1 start in 200 with `host="127.0.0.1"`, and in most starts with a
  host name such as `localhost`. `start_server()` now returns once wse
  listens, and raises `RuntimeError` when wse can't bind the port, or binds
  it only after 10 seconds; it returned before, and the cable served
  nothing (see Upgrading).
- A broadcast forwarded to the cable process (from a task worker, a shell or
  another copy of `PROCESSES`) could reach the clients twice. The cable
  process answers once it has delivered it, and delivery waits while the
  stream's subscribers are behind (backpressure, up to a second per
  broadcast); an answer later than 2 seconds, as for a `batch()` of three
  such broadcasts, made the sender send it again, and the copy was
  delivered too, with a warning that the cable process could not be
  reached. Each forwarded broadcast now carries an id, and the cable
  process ignores one it has already received.
- The debug error and not-found pages showed a `password` value that was not
  a string as it was (`{"password": ["hunter2"]}` as `['hunter2']`), a
  `SECRET_KEYS` that was a tuple or a string in full, the values of a dict
  under `SECRET_KEYS` or a `password` key in full unless their own key was
  `password` (`{"password": {"db": "hunter2"}}`), and a `password` key in a
  dict inside a list or tuple in full (`{"DATABASES": [{"password":
  "hunter2"}]}`). An `int` or `float` password or `SECRET_KEYS` item raised
  `TypeError`, and a config key that was not a string `AttributeError`, so
  the page was not shown. Now the value of every `SECRET_KEYS` key and every
  `password` key (in any letter case) is redacted, in the config and in
  every dict, list, tuple or named tuple inside it, at any depth: every
  value under such a key, at any depth, is shown as its text with each
  character after the fourth replaced by `▒` (`12345678` as `1234▒▒▒▒`),
  except an empty or false value (`""`, `None`, `0`, `False`), which is
  kept. Other values are shown as they are. The pages show plain copies: a
  dict as a `dict`, a named tuple as a `dict` of its fields (so a field
  named `password` is redacted), any other tuple as a `tuple`, a list as a
  `list`. The redaction never raises and reads a bounded number of values:
  it shows `▒▒▒▒` for a container that contains itself (a cycle), for a
  container more than 32 levels deep, for every value after the first 10
  000, and for a value or key that raises when it is read.
- `@router.resource()` on a controller that inherits an action from a parent
  controller named the route after the decorated class (`Article.index`),
  but ran the request on an instance of the parent
  (`ApplicationController`): without the `before` and `after` callbacks of
  the subclass, and looking up only the parent's views. `url_for` with an
  object did not read the placeholder `:article_id` from the object's `id`,
  as it does for the class's own actions. `resource()` now gives each route
  its class (the new `controller` argument of `Route`, which raises
  `ConfigError` when `to` is not the method that this class has under the
  action's name), so the request runs on an instance of the decorated class,
  with its callbacks and its views (`article/`, then the parents' folders),
  and `:article_id` is read from `id` too. `proper routes` shows that class
  in its TO column (`ArticleController.index`). A route made from a method
  object (`router.get("feed")(ArticleController.index)`, `Route(to=...)`)
  still belongs to the class that defines the method (`Application.index`):
  a function doesn't know the class it was read from.

## 0.34

### Added

- `app.around_request(func)`: registers a function that wraps the whole run
  of every request, called as `func(request, response, call_next)`. If the
  request failed, `response.error` has the exception, even after the error
  page was rendered. Meant for monitoring integrations (timing, tracing,
  error reporting).

## 0.33

### ⚠️ Upgrading: move the uploaded files

The `Disk` storage service now stores each file at
`<root>/<id[:2]>/<id[2:4]>/<id>/<filename>` instead of
`<root>/<id[:2]>/<id[2:4]>/<filename>`.

The files saved by older versions stay at the old path, and this version
doesn't look for them there: **until they are moved, every existing upload
of the app is "not found"**. Run this once, right after upgrading, in every
app that uses `Disk` storage:

```python
from myapp.models import Attachment

for attachment in Attachment.select():
    service = attachment.service
    if hasattr(service, "move_from_legacy_path"):
        service.move_from_legacy_path(attachment)
```

`move_from_legacy_path` skips the files already moved, so it can run again.
Apps that only use `S3` storage don't need it.

### Fixed

- `Disk`: two attachments with the same filename whose ids start with the
  same four characters shared a file, and one overwrote the other. Every
  variant was named `variant.<ext>`, so it happened often with variants and
  pages showed the wrong images. The full id is now part of the path (see
  above), and `purge` also removes the empty folders.
- A request whose `Accept` header lists other formats before `*/*` (e.g.
  `application/json, text/plain, */*`, what many HTTP libraries send) failed
  with a 500 when the action only had an HTML template. `*/*` now falls back
  to the default format after the listed ones.
- When an action has a template but none in a format the client accepts,
  the response is now `406 Not Acceptable` with an empty body, instead of a
  500. An error page keeps its status (e.g. a 404 stays a 404). An action
  without a template in the default format still raises
  `ComponentNotFoundError`, because that's a missing view.
- The blueprint's `public/index`, `public/not_found` and `public/error`
  templates have format-less names (`.jx`, not `.html.jx`), so new apps
  render them whatever the client accepts.
- Pagination: a missing page number no longer logs an
  "invalid page number: None" warning.

### Changed

- The pings of the cable are wse's (`{"c": "WSE", "t": "ping"}`), every
  `CABLE_PING_INTERVAL` seconds, instead of a second ping from a Python
  thread. `CABLE_PING_INTERVAL` is now a whole number of seconds, at least 1
  and less than the cable's `idle_timeout` (60), and `0` is a `ConfigError`
  instead of "no pings". `cable.js` takes a connection for dead after three
  intervals of silence (at least 10 seconds). Apps created before need the
  new `assets/js/cable.js`.
- The `CABLE_*` settings are checked at startup when a cable is set: the
  port, the path, the ping interval against `idle_timeout`, and the
  slow-client limits. `CABLE` may not set wse's `ping_interval`,
  `allowed_origins` or `recovery_enabled`, which `CABLE_PING_INTERVAL`,
  `CABLE_ALLOWED_ORIGINS` and the `recovery` option decide.
- Image variants are named after the original file
  (`<original name>.<ext>`) instead of `variant.<ext>`.

### Added

- `Disk.move_from_legacy_path(attachment)`, to move a file stored by an
  older version to its current path.
