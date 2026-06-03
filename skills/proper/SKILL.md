---
name: proper
description: Use when building features, adding resources, writing controllers/models/forms/views, or working with addons (auth, storage, i18n, channels) in a Proper web framework application. Also use when the user asks about Proper framework conventions or patterns.
user-invocable: false
last_verified: 2026-06-03
---

# Proper Framework Development

You are working on **Proper**, an opinionated Python web framework. When generating code for a Proper app, follow the conventions below exactly.

For the actual source code of any generated file, **read it directly from the app** rather than guessing its contents.

> **Context budget:** Read ONLY the doc(s) relevant to the current task — typically 1, at most 2–3. The full doc set is ~10k lines; loading it all wastes context. For tasks that combine addons (e.g. a resource with auth and file uploads), read the primary doc first, then the relevant addon doc(s).

## Architecture Overview

A Proper app follows a resource-oriented MVC pattern. Here is how the pieces connect:

```
Request
  │
  ▼
Router  ─────────────────  routes.py maps URLs to controller actions
  │
  ▼
Controller  ──────────────  receives the request, runs `before` callbacks
  │
  ├──▶ Model (Peewee)  ──  queries/mutates the database
  │
  ├──▶ Form (Formidable)   validates input, saves to model
  │
  ├──▶ View (Jx/Jinja)  ─  renders HTML using components and layouts
  │
  └──▶ Response  ─────────  HTML page, redirect, or JSON
```

**Key files per resource** (e.g. `Comment`):

| Layer | File |
|-------|------|
| Route | `routes.py` — `resources("Comment")` |
| Controller | `controllers/comment_controller.py` |
| Model | `models/comment.py` |
| Form | `forms/comment.py` |
| Views | `views/comment/{index,show,new,edit}.jx` |
| Tests | `tests/test_comment.py` |

**Cross-cutting systems** — these are available from any controller via `self` or the app context:

- **Sessions / Auth** — `self.session`, auth concern methods (`current_user`, `sign_in`)
- **Caching** — `app.cache` key-value store, `{% cache %}` template tag
- **Background tasks** — `app.queue` (Huey), `@task()` decorator
- **Emails** — `EmailMessage` composed and sent via mailer backends
- **Storage** — `Attachment` model for file uploads (S3 or disk)
- **Rich Text** — `RichTextField` for formatted documents with embedded attachments (Lexxy editor)
- **Channels** — WebSocket channels for real-time updates

## Which Doc to Read

| Task | Read | Run |
|------|------|-----|
| Add a page with a DB model | [generated_app.md](generated_app.md) | `proper g resource NAME attrs...` |
| Add a controller without a model | [generated_app.md](generated_app.md) | `proper g controller NAME attrs...` |
| Add only a model | [models.md](models.md) | `proper g model NAME attrs...` |
| Add seed data (default roles, reference rows) | [models.md — Seeds](models.md#seeds) | `proper g seed NAME` then `proper db seed` |
| Add an email | [emails.md](emails.md) | `proper g email NAME` |
| Add authentication | [auth.md](auth.md) | `proper install auth && proper db migrate` |
| Add file uploads | [storage.md](storage.md) | `proper install storage && proper db migrate` |
| Add rich text fields with embedded files | [rich_text.md](rich_text.md) | `proper install rich_text && proper db migrate` |
| Add i18n | [i18n.md](i18n.md) | `proper install i18n` |
| Add WebSockets | [channels.md](channels.md) | `proper install channels` |
| Write or fix tests | [testing.md](testing.md) | `uv run pytest` |
| Customize forms / validation | [forms.md](forms.md) | — |
| Build Jinja components | [jx.md](jx.md) | — |
| Add routes or understand URL generation | [routing.md](routing.md) | `proper routes` |
| Build a JSON API or add JSON responses | [controllers.md](controllers.md) | — |
| Controller behavior (callbacks, rendering, concerns) | [controllers.md](controllers.md) | — |
| Security (CSRF, rate limiting, sessions, cookies) | [security.md](security.md) | — |
| Caching (fragment, HTTP, Russian doll) | [caching.md](caching.md) | — |
| Background jobs | [tasks.md](tasks.md) | — |
| Send emails | [emails.md](emails.md) | — |
| Understand the request lifecycle | [app.md](app.md) | — |
| Custom concerns (shared controller logic) | [controllers.md](controllers.md) | — |
| Quick reference (all public exports) | [api.md](api.md) | — |

## Standard Workflow

This is the typical sequence for adding a new feature that involves a database-backed resource.

### Adding a resource (model + controller + views)

1. **Generate** — `proper g resource Comment body:text user:fk-User,backref:comments,on_delete:CASCADE post:fk-Post,backref:comments,on_delete:CASCADE --migration`
2. **Edit model** — open `models/comment.py`, adjust fields if needed
3. **Edit form** — open `forms/comment.py`, add/remove fields, add custom validators
4. **Edit controller** — open `controllers/comment_controller.py`, adjust `before` callbacks and actions
5. **Edit views** — open `views/comment/*.jx`, update the markup and form fields
6. **Migrate** — `proper db migrate`
7. **Write tests** — open `tests/test_comment.py`, add full CRUD coverage
8. **Run tests** — `uv run pytest`

### Adding a controller without a model

Use when the model already exists or no model is needed:

1. **Generate** — `proper g controller Dashboard --only=index`
2. **Edit the generated files** as above (controller, form, views)
3. **Write tests and run them**

### Adding only a model

1. **Generate** — `proper g model Tag name:str,unique --migration`
2. **Migrate** — `proper db migrate`
3. **Write model-level tests**

### Key rules during the workflow

- Always read the generated files before editing — don't guess their contents
- After any generator, check `controllers/__init__.py` and `models/__init__.py` to verify imports were added
- New fields on existing tables need `default=...` or `null=True`
- Run `proper routes` to verify the routes look correct
- See [generated_app.md — Generator Quick Reference](generated_app.md#generator-quick-reference) for full generator options
