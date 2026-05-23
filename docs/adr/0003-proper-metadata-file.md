# ADR-0003: Track Installed Addons in `.proper`, not a DB Table

**Status:** Accepted (2026-05-21)


## Context

Addons that depend on other addons need to know which addons are
already installed. The rich text addon, for instance, depends on
storage (it builds on the `Attachment` model). If storage isn't
present, the installer should either fail loudly or auto-install
storage first - and either way it needs to know.

Three places this state can live:

- **Heuristics** - does `models/attachment.py` exist on disk? Is the
  `attachment` table in the database?
- **A database table** that records every install, the way Django's
  `django_migrations` records migrations.
- **A version-controlled file** at the app root that lists installed
  addons.


## Decision

A `.proper` JSON file at `app.root_path/.proper`, committed to version
control:

```json
{
  "addons": {
    "storage":   {"version": "0.10.0", "installed_at": "2026-05-20T10:00:00Z"},
    "rich_text": {"version": "0.10.0", "installed_at": "2026-05-20T11:00:00Z"}
  }
}
```

Helpers in `proper.install.metadata`:

- `is_installed(app, addon)` - boolean check, used for dependency
  resolution.
- `record_install(app, addon, version=None, config=None)` - upserts an
  entry; defaults `version` to the running Proper version.
- `load_metadata(app)` - returns the parsed dict.

Atomic writes (write to `.proper.tmp`, rename) prevent half-written
files on crash.


## Consequences

- A fresh `git clone` of an app gives the next developer accurate
  "which addons are installed" state without needing the database to
  be reachable or migrated.
- The installer flow is straightforward: every `install()` ends with
  `record_install(app, "<name>")`. Addons that depend on others check
  `is_installed(app, "<dep>")` and either fail or recurse into the
  dependency's installer.
- The file is editable and inspectable. If someone really wants to
  mark an addon as installed without running the installer (e.g.
  rebuilding an app), they can - same as committing a stub migration
  file. Not encouraged, but not blocked.
- Idempotent re-install: running `proper install rich_text` twice
  upserts the entry on the second call rather than duplicating.
- One trade-off: the file can drift from reality if a user manually
  deletes the addon's code without updating `.proper`. The cost of
  that drift is "the installer thinks it doesn't need to install
  again" - a minor inconvenience, never a correctness issue.


## Alternatives considered

- **Heuristics (file or table presence checks).** Rejected because
  every variant is brittle. File presence answers "is the addon's
  code here?" which is a structural property the user can mutate;
  table presence answers "is the schema applied?" which is a runtime
  property that needs a live DB.
- **DB table (`proper_metadata`).** Rejected for two reasons. First,
  fresh-clone state desync: cloning the code gives you accurate file
  layout but an empty database, so the table would lie. Second,
  bootstrap circularity: a DB-table approach needs a DB connection
  before the first addon is installed, which is exactly when the user
  has just run `uvx proper_new` and may not have a database yet.
