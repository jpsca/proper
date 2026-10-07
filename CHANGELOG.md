# Changelog

All notable changes to Proper are documented in this file.

## Unreleased

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

Three things to change:

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

Without the CDN's ranges, `X-Forwarded-For` arrives as
`<visitor>, <CDN edge>`, and `remote_ip` is the CDN edge's address for every
visitor (it was the visitor's, the leftmost). The default `rate_limit` then
puts every visitor behind one edge in one bucket, so they all get 429s
together, and the auth sessions record the CDN's address.

Three more changes in how `remote_ip` reads the headers:

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
- An `X-Forwarded-For` address is returned without a port that a proxy
  added (`203.0.113.5:51234` gives `203.0.113.5`), and an IPv4-mapped
  address as IPv4 (`::ffff:203.0.113.5` gives `203.0.113.5`). A
  `Forwarded` value is still returned as written.

Make the proxy drop the request headers with an underscore in the name,
such as `X_Forwarded_For`. The WSGI server gives the app `X-Forwarded-For`
and `X_Forwarded_For` under the same name, so the app can't tell the
client's header from the proxy's, and Granian can keep the client's value.
nginx drops these headers unless `underscores_in_headers` is on; a proxy
built on Go's `httputil.ReverseProxy` passes them through.

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
`1.2.3.4`), and it wins over `Forwarded`.

### ⚠️ Upgrading: conditional requests follow RFC 9110 more closely

`response.is_fresh()`, and so the automatic `304 Not Modified` after an
action and the return value of `fresh_when()`, now follow these rules of
RFC 9110:

- A response can be fresh only for a `GET` or `HEAD` request and with a
  2xx status. Before, a `POST` with a matching `If-None-Match`, or an
  action that set a 404 or a redirect, could get its status replaced by
  304 and lose its body. Now that response is sent in full, and
  `fresh_when()` and `is_fresh()` return `False` for it. If an action
  used their return value on another method or status, it must not
  count on `True` there any more.
- `If-Modified-Since` is ignored when the request has an
  `If-None-Match`. Before, an ETag that didn't match could still get a 304
  from the date. Static files have no ETag, so a request for one that
  carries an `If-None-Match` now always gets a 200. If a proxy or CDN in
  front of the app adds its own `If-None-Match` to the requests it
  revalidates, make it send only `If-Modified-Since` for static files, or
  they lose their 304s.
- `If-None-Match` uses the weak comparison (`W/"x"` matches `"x"`), and
  `If-None-Match: *` matches any response with an ETag. Before, only the
  exact string matched, so more requests now get a 304.

Two RFC 9110 rules are not applied: `If-None-Match: *` matches only a
response with an ETag (the RFC matches any existing resource), and a request
with another method whose `If-None-Match` matches gets the response as it
is, not a `412 Precondition Failed`.

A response with the status 304 now always goes out without a body, also
when the action sets the status itself: the body is emptied, whatever the
action returned, and no template is rendered. Before, the body was emptied
only when the request's headers made the response fresh.

### Removed

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
- `url_for` copied the text of the route as written, so a route such as
  `/über/:id` or `/my files/:id` gave an invalid URL, and a non-latin-1
  character in it broke the `Location` header of a redirect. The text is now
  percent-encoded as the values are: `/%C3%BCber/42`.
- `url_for` (and the host for `_full=True`) read the route with
  `string.Template` rules, not the placeholder rules used for matching: `:ID`
  in a path raised `KeyError`, `10:30` or a host with a port
  (`localhost:5000`) raised `ValueError`, `/:a<int>bc` raised `KeyError`,
  and `/a::b` lost a `:`. The text that is not a placeholder is now copied
  as written. `Route` no longer uses `RouteTemplate`, which is kept for
  compatibility.
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
- A session cookie whose signed value was not a JSON object (a string, a
  number, `true`) was a 500, and a list of pairs became a session. Any value
  that is not an object is now no session, as a bad signature is.
- A malformed parameter in `Accept`, `Accept-Encoding` or `Accept-Language`
  was a 500: one without a value (`text/html;level`), an empty one
  (`text/html;`), or a `q` that is not a number (`q=abc`). Such a parameter
  is now ignored; a `q` that is not a number from 0 to 1 counts as 1.
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
  UTC; it is now converted to UTC, and ignored if the conversion takes it
  past the year 9999 or before the year 1.
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
