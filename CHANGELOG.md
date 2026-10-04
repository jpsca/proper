# Changelog

All notable changes to Proper are documented in this file.

## Unreleased

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
