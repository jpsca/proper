# Changelog

All notable changes to Proper are documented in this file.

## Unreleased

### ⚠️ Upgrading: the WebSockets need `WseCable`

The in-process cable is gone, and with it RSGI: `proper run` always serves
over WSGI, and the only cable that serves WebSockets is `WseCable`
(`RedisCable` on several machines). An app that used `CABLE = {}` with a
`CABLE_PORT` now fails to start with a `ConfigError`. Install `proper-wse`
and set the cable:

```bash
uv add proper-wse
```

```python {title="config/channels.py"}
CABLE = {"type": "proper.channels.wse.WseCable"}
```

### Removed

- The in-process cable and its WebSocket process: `proper.core.app_ws`, and
  the second, RSGI, process that `proper run` started on `CABLE_PORT`.
  `CABLE = {}` (the default) is now a `Cable` that serves no WebSockets: a
  `broadcast()` reaches no one. `CABLE_PORT` with an empty `CABLE` is a
  `ConfigError`.
- RSGI: `App.__rsgi__`, `App.startup()` and `App.shutdown()` (`app.lower()`
  stays), the app's own thread pool, and `Cable.start()`/`Cable.stop()`
  (`WseCable` has `start_server()`/`stop_server()`, which `proper run`
  calls).
- The settings `INTERFACE`, `THREAD_WAIT_WARNING`, `LOOP_STALL_WARNING` and
  `CABLE_MAX_PENDING` (`CABLE_MAX_PENDING_BYTES` and `CABLE_STALL_TIMEOUT`
  stay).
- From `proper.test_client`: `make_test_scope`, `make_test_ws_scope`,
  `HttpProtocolStub` and `WsProtocolStub`. `client.websocket()` always runs
  the app's `WseCable` from memory, and no longer takes a path, which the
  in-memory server doesn't use; with a cable that serves no WebSockets,
  `connect()` raises `RuntimeError`.

### Added

- `proper.db.prepare(query)` and `proper.db.Param`: prepared queries, compiled
  to SQL once and executed many times with new values, on the released Peewee.

### Fixed

- A channel registered under another name (`@router.channel("chat")`) sent
  its `send()` messages with the class name, so `cable.js` couldn't find the
  subscription and dropped them. `channel_name` is now the name the client
  subscribed with.
- wse closed every connection that sent it nothing for a minute, so a page
  that only listened reconnected every minute or so, losing the broadcasts
  sent meanwhile. `cable.js` now answers wse's pings. Apps created before
  need the new `assets/js/cable.js`: copy it from Proper's
  `_blueprints/addon_channels/assets/js/cable.js`.
- A client could call a channel's `find_user()` as an action. It is now
  refused, like the other channel internals.
- `WseCable`: what a channel set on `current` in one command (such as
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

- Image variants are named after the original file
  (`<original name>.<ext>`) instead of `variant.<ext>`.

### Added

- `Disk.move_from_legacy_path(attachment)`, to move a file stored by an
  older version to its current path.
