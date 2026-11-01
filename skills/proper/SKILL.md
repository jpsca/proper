---
name: proper
description: Use when building features, adding resources, writing controllers/models/forms/views, or working with addons (auth, storage, i18n, channels) in a Proper web framework application. Also use when the user asks about Proper framework conventions or patterns.
user-invocable: false
proper_version: 0.48.0
last_verified: 2026-11-01
sources:
  - src/proper/generators
  - blueprint/tests
---

# Proper Framework Development

You are working on **Proper**, an opinionated Python web framework. You can know it because "proper" is one of the dependencies in the `pyproject.toml` file, or because the user tells you they are building a Proper app.

When generating code for a Proper app, follow the conventions below exactly.

For the actual source code of any generated file, **read it directly from the app** rather than guessing its contents.

## How to Read This Skill

- Each doc covers one task and is short (under 600 lines, most under 500). Read ONLY the doc(s) for the current task: usually 1, at most 2 or 3. For a task that combines addons (a resource with auth and file uploads), read the primary doc first, then the addon doc(s).
- Each topic lives in one doc. Other docs mention it in one line and link to it; follow the link instead of guessing.
- `reference/` holds lookup tables (every attribute of `Request`/`Response`, every status constant, the cable's JSON frames). Open one only to confirm an exact name or signature. The guides are enough for everything else.
- This skill describes Proper (`proper_version` above). The app's version is `uv run python -c "from importlib.metadata import version; print(version('proper'))"`. With an older Proper, the generated files and `proper --help` win over this skill where they differ.
- Working examples of patterns not covered here (OAuth sign-in with Google and GitHub on top of `proper install auth`, among others) are in the [proper-examples](https://github.com/jpsca/proper-examples) repository. Check its README before building one of those from scratch.

## Architecture Overview

A Proper app follows a resource-oriented MVC pattern. Here is how the pieces connect:

```
Request
  │
  ▼
Router  ─────────────────  router.py maps URLs to controller actions
  │
  ▼
Controller  ──────────────  receives the request, runs `before` callbacks
  │
  ├──▶ Model (Peewee)  ──  queries/mutates the database
  │
  ├──▶ Form (Formidable)   validates input, saves to model
  │
  ├──▶ View (Jx)        ─  renders HTML using components and layouts
  │
  └──▶ Response  ─────────  HTML page, redirect, or JSON
```

**Key files per resource** (e.g. `Comment`):

| Layer | File |
|-------|------|
| Route | `@router.resource("comments")` on the controller class |
| Controller | `controllers/comment_controller.py` |
| Model | `models/comment.py` |
| Form | `forms/comment.py` |
| Views | `views/comment/{index,show,new,edit}.jx` |
| Tests | `tests/controllers/test_comment.py` |

**Cross-cutting systems**, available from any controller via `self` or the `current` context:

- **Sessions / Auth**: `self.request.session`, `current.user`, `sign_in`
- **Caching**: `app.cache` key-value store, `{% cache %}` template tag
- **Background tasks**: `app.queue` (Huey), `@task()` decorator
- **Emails**: `EmailMessage` composed and sent via mailer backends
- **Storage**: `Attachment` model for file uploads (S3 or disk)
- **Rich Text**: `RichTextField` for formatted documents with embedded attachments (Lexxy editor)
- **Channels**: WebSocket channels for real-time updates, over the cable

## Which Doc to Read

Core:

| Task | Read | Run |
|------|------|-----|
| Create a new app from scratch | [app.md, Setup](app.md#setup) | `uvx proper_new myapp` |
| Understand the request lifecycle, `current`, config keys, lifecycle hooks | [app.md](app.md) | — |
| Run, check, serve or log the app | [cli.md](cli.md) | `proper run`, `proper check` |
| Deploy: Dockerfile, compose, nginx, sizing, prod config, `.env`, checklist | [deployment.md](deployment.md) | `docker compose build`, `proper db prepare` |
| Generator syntax (`title:str,unique`, `user:fk-User`, `--only`, `--namespace`) | [generators.md](generators.md) | `proper g --help` |
| Write a controller: CRUD, state-change resources, params, the generated code | [controllers.md](controllers.md) | `proper g resource NAME ...` |
| What an action returns: templates, JSON, Turbo Streams, redirects, flash, HTTP errors | [rendering.md](rendering.md) | — |
| `before`/`after` callbacks, concerns, pagination, rate limiting, origin protection | [concerns.md](concerns.md) | — |
| An admin interface next to the public one (`/admin/posts`) | [namespacing.md](namespacing.md) | `proper g controller NAME --namespace=admin` |
| Add routes: resources, individual, scoped, host-based, redirects, method override | [routing.md](routing.md) | `proper routes` |
| Build URLs: `url_for`, `url_is`, asset URLs | [urls.md](urls.md) | — |
| Define a model, fields, relationships, queries | [models.md](models.md) | `proper g model NAME attrs...` |
| Model mixins, `@scope` queries, signed tokens for a record | [models_advanced.md](models_advanced.md) | — |
| Database config, migrations, seeds | [migrations.md](migrations.md) | `proper db create "..."`, `proper db migrate`, `proper db seed` |
| Customize forms / validation | [forms.md](forms.md) | — |
| Build Jx components | [jx.md](jx.md) | — |
| Layouts, import maps, Stimulus controllers, the `flashes.jx` component | [frontend.md](frontend.md) | — |
| Turbo Drive, Frames, Streams (live UI, frame navigation, stream responses) | [turbo.md](turbo.md) | — |
| Write or fix tests | [testing.md](testing.md) | `uv run pytest` |
| Security: CSRF, sessions, cookies, secret keys, size limits, proxies | [security.md](security.md) | — |
| Caching: store API, fragment, Russian doll, HTTP caching (`fresh_when`) | [caching.md](caching.md) | — |
| Background jobs | [tasks.md](tasks.md) | — |
| Send emails | [emails.md](emails.md) | `proper g email NAME` |

Addons:

| Task | Read | Run |
|------|------|-----|
| Add authentication | [auth.md](auth.md) | `proper install auth && proper db migrate` |
| Add file uploads | [storage.md](storage.md) | `proper install storage && proper db migrate` |
| Image variants, previews of PDFs/videos, a custom storage service | [storage_advanced.md](storage_advanced.md) | — |
| Add rich text fields with embedded files | [rich_text.md](rich_text.md) | `proper install rich_text && proper db migrate` |
| Add i18n | [i18n.md](i18n.md) | `proper install i18n` |
| Add WebSockets: write a channel, broadcast, presence, test it | [channels.md](channels.md) | `proper install channels` |
| The `cable.js` client, `CABLE_*` settings, RedisCable, a full chat example | [cable.md](cable.md) | — |

Reference (exact names only):

| Need | Read |
|------|------|
| Every attribute and method of `Controller`, `App`, `Request`, `Response`; units; `DotDict`/`MultiDict` | [reference/api.md](reference/api.md) |
| Every `proper.status` constant | [reference/status_codes.md](reference/status_codes.md) |
| Every option of every form field (`AttachmentField`, `NestedForms`, ...) | [reference/form_fields.md](reference/form_fields.md) |
| The Jx `Catalog` class: globals, filters, block tags, `render()` | [reference/jx_catalog.md](reference/jx_catalog.md) |
| The JSON frames between `cable.js` and the cable | [reference/cable_protocol.md](reference/cable_protocol.md) |

## Standard Workflow

This is the typical sequence for adding a new feature that involves a database-backed resource.

### Creating a new app

The first step for any new Proper app. Requires `uv`/`uvx` ([install guide](https://docs.astral.sh/uv/getting-started/installation/)).

1. **Scaffold**: `uvx proper_new myapp` (generates the full project: `config/`, `controllers/`, `models/`, `views/`, `forms/`, `router.py`, `db/`, `tests/`)
2. **Enter the project**: `cd myapp`
3. **Verify the baseline**: `uv run pytest`
4. Add your first resource (see below)

### Adding a resource (model + controller + views)

1. **Generate**: `proper g resource Comment body:text user:fk-User,backref:comments,on_delete:CASCADE post:fk-Post,backref:comments,on_delete:CASCADE --migration`
2. **Edit model**: open `models/comment.py`, adjust fields if needed
3. **Edit form**: open `forms/comment.py`, add/remove fields, add custom validators
4. **Edit controller**: open `controllers/comment_controller.py`, adjust the actions
5. **Edit views**: open `views/comment/*.jx`, update the markup and form fields
6. **Migrate**: `proper db migrate`
7. **Write tests**: open `tests/controllers/test_comment.py`, add full CRUD coverage
8. **Run tests**: `uv run pytest`

### Adding a controller without a model

Use when the model already exists or no model is needed:

1. **Generate**: `proper g controller Dashboard --only=index`
2. **Edit the generated files** as above (controller, form, views)
3. **Write tests and run them**

### Adding only a model

1. **Generate**: `proper g model Tag name:str,unique --migration`
2. **Migrate**: `proper db migrate`
3. **Write model-level tests**

### Key rules during the workflow

- Always read the generated files before editing; don't guess their contents
- After any generator, check `controllers/__init__.py` and `models/__init__.py` to verify imports were added
- New fields on existing tables need `default=...` or `null=True`
- Run `proper routes` to verify the routes look correct
- Run `proper check` after a change and fix every error it lists (see [cli.md](cli.md#checking))

## Pitfalls

What Rails, Django or Flask habits get wrong in Proper:

- Table names are Peewee's default, the class name lowercased (`BlogPost` → `blogpost`). Nothing is pluralized.
- Controllers are synchronous: no `async`/`await` in an action.
- Nothing halts inside an action: `return self.render(...)` and `return self.redo()`, or the code after them runs.
- The signed-in user is `current.user`; `current.auth_session` is the session row, not the user.
- Sign-out is `DELETE /sign-in` (`url_for("Session.delete")`); there is no `/sign-out`.
- Custom error handlers run only with `DEBUG` off; in development the debug page shows instead.
- Views are Jx components: no `include`, `extends` or `block`; layouts are components too.
- Live UI is Turbo (Drive, Frames, Streams), not htmx.
- JSON columns are `pw.JSONField`; `proper.JSONField` exists for backwards compatibility only.
- `app.i18n.format_date()` takes a datetime too; there is no `format_datetime`.
- The `TestClient` does not follow redirects: assert the 303 and the `Location`.
- `client.sign_in(session)` takes a `Session` row; use the `signed_client` fixture.
- Generated tests live in `tests/controllers/`; run them with `uv run pytest`.
