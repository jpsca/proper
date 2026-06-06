---
title: Testing Proper Applications
description: |
  How to test a Proper application end-to-end with the bundled `TestClient`. Covers the generated test setup, the `db_reset` transactional fixture, making requests of every HTTP verb, uploading files, asserting on the response, signing users in, and exercising models, forms, emails, background tasks, and WebSocket channels.
number_headers: true
---

# Testing Proper Applications

A web application that you can't change without fear of breaking it is a web application that stops moving. Tests are how you keep that fear in proportion: not "I think this still works" but "the suite tells me it does." The earlier you write them and the cheaper they are to run, the more often you'll actually run them - and the more you'll trust the result.

Proper takes that idea seriously. The framework ships a `TestClient` that drives your app through the **full ASGI stack** - the same router, middleware, controllers, sessions, and database connections that run in production. There is no separate test server to start and no internals to mock. A test is a Python function that calls the client, gets a response, and asserts on it. The generated `tests/conftest.py` wires up a transactional database fixture so tests don't have to clean up after themselves. In the test environment, the cache is a no-op, background tasks run inline, and emails go to an in-memory outbox - so you can assert on the side effects without standing up Redis, a worker, or an SMTP server.

After reading this guide, you will know:

- The shape of a Proper test - the `TestClient`, the `db_reset` fixture, what runs differently in the test environment, and the conventions a generator follows.
- How to drive the app through every HTTP verb, upload files, send headers, and read what came back.
- How to sign users in, test channels, and assert on emails and background work.
- The common pitfalls - redirects that aren't followed, the outbox that accumulates, the safety check that prevents wiping a real database.

----

## The shape of a Proper test

Before the reference, here is one full test from end to end. It exercises a `Photo` controller's `create` action: posts a form, follows the resulting redirect, and checks that the record landed in the database. Every piece in this test is something the generator gave you, or something you'd write naturally.

```python {title="tests/test_photos.py"}
from myapp.models import Photo


def test_create_redirects_and_persists(client):
    result = client.post("/photos", body={"title": "Sunset"})

    assert result.status == 303
    assert result.headers["location"] == "/photos/1"
    assert Photo.select().where(Photo.title == "Sunset").count() == 1
```

Three things to notice:

- **`client` is a fixture**, provided by the generated `tests/conftest.py`. You don't construct a `TestClient` per test - the fixture hands you a fresh one bound to your app.
- **No database argument is required**, but a database is available. The generated conftest marks its `db_reset` fixture as `autouse=True`, so every test runs inside a transaction that is rolled back when the test ends. You read and write the database freely; the next test sees a clean slate.
- **The response is a plain object**. `result.status` is the HTTP status code. `result.headers` is a case-insensitive dict. `result.body` is the rendered response as a string. There is no `.json()` method to await, no test-specific response wrapper - the same data the browser would see, in Python form.

The whole rest of this guide unpacks those three lines.

----

## Setup

A freshly generated Proper application is already set up for testing. There are no extra packages to install, no test runner to configure, no test-specific entry point to wire up. The pieces are:

- The **test environment**, selected by `APP_ENV=test`, which swaps in fast in-memory replacements for the database, queue, cache, and mailer.
- The **`tests/` directory**, with a `conftest.py` that provides the `client` and `db_reset` fixtures and a stub `test_public.py` to confirm the harness works.
- **pytest** as the runner, invoked through `uv run pytest`.

### The test environment

`config/main.py` and `config/storage.py` both check `APP_ENV` and override defaults when it equals `"test"`. The generated overrides are:

```python {title="config/storage.py"}
if env == "test":
    DATABASES["main"] = {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": ":memory:",
    }

    QUEUE = {
        "type": "huey.MemoryHuey",
        "immediate": True,
        "immediate_use_memory": True,
    }

    CACHE = {
        "type": "proper.cache.NoCache",
    }
```

```python {title="config/main.py"}
# MAILERS lists the available backends by name; MAILER picks the active one.
MAILERS = {
    "console": {"type": "proper.emails.ToConsoleMailer"},
    "memory": {"type": "proper.emails.ToMemoryMailer"},
    # ...
}
MAILER = "console"

if env == "test":
    MAILER = "memory"
```

Each switch matters:

Override          | Effect
----------------- | ------
`:memory:` SQLite | The database lives in RAM. Suites of hundreds of tests finish in seconds, and nothing on disk to clean up.
`MemoryHuey` with `immediate=True` | Background tasks run inline, in the calling process, the moment they are enqueued. `send_later()` behaves like `send()`. No worker required.
`NoCache` | `app.cache.set(...)` is a no-op; `app.cache.get(...)` always returns the default. Test assertions never see stale cached state from a previous test.
`ToMemoryMailer` | Sent emails go to `app.mailer.outbox` instead of an SMTP server. You inspect them like any other Python list.

How does `APP_ENV=test` actually get set? The test package's `__init__.py` does it before any other import:

```python {title="tests/__init__.py"}
import os


os.environ["APP_ENV"] = "test"
```

Because pytest imports the `tests` package before it imports any test module (and because the test modules import your app, which reads the config), the variable is set in time. You normally don't need to touch this file.

### `tests/conftest.py`

The generated conftest is short. Most of it is fixture wiring:

```python {title="tests/conftest.py"}
import os

import pytest
from proper import TestClient

from myapp.main import app
from myapp.models import db
from myapp.models.base import BaseModel


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def db_setup():
    # better to be safe than sorry
    assert os.getenv("APP_ENV") == "test"
    assert "test" in db.database or "memory" in db.database

    db.connect(reuse_if_open=True)

    models = BaseModel.__subclasses__()
    db.drop_tables(models)
    db.create_tables(models, safe=True)
    load_fixtures()

    yield

    db.drop_tables(models)
    db.close()
    if os.path.exists(db.database):
        os.remove(db.database)


@pytest.fixture(autouse=True)
def db_reset(db_setup):
    with db.atomic() as transaction:
        yield
        transaction.rollback()


def load_fixtures():
    pass
```

There are three fixtures, each doing one job.

#### The `client` fixture

```python
@pytest.fixture()
def client():
    return TestClient(app)
```

A function-scope fixture that hands you a `TestClient` bound to your real app. You can also construct one yourself - `TestClient(app)` is cheap and has no per-request state - but the fixture is what every generated test depends on, so use it for consistency:

```python
def test_index(client):
    result = client.get("/")
    assert result.status == 200
```

#### The `db_setup` fixture (session scope)

```python
@pytest.fixture(scope="session")
def db_setup():
    assert os.getenv("APP_ENV") == "test"
    assert "test" in db.database or "memory" in db.database

    db.connect(reuse_if_open=True)

    models = BaseModel.__subclasses__()
    db.drop_tables(models)
    db.create_tables(models, safe=True)
    load_fixtures()

    yield

    db.drop_tables(models)
    db.close()
    if os.path.exists(db.database):
        os.remove(db.database)
```

Runs **once per test session**. The steps, in order:

1. **Safety check.** Two assertions refuse to run unless `APP_ENV` is `"test"` *and* `db.database` looks like a test database - its name contains `test`, or it is an in-memory database (`"memory"` matches `:memory:`). This is the line standing between you and the day someone runs the test suite against production. Leave it in place.
2. **Connection.** A connection is opened on the test thread and held for the whole session (`reuse_if_open=True`). This keeps a shared in-memory database alive and supports backends configured with `autoconnect=False`.
3. **Schema reset.** Every subclass of `BaseModel` is dropped and recreated. No Alembic-style migrations, no fixture data left over from a previous run.
4. **Seed data.** `load_fixtures()` is called - empty by default - so you can populate the database with rows that every test should see.

On teardown the tables are dropped, the connection is closed, and the database file (if any) is removed.

#### The `db_reset` fixture (autouse, per test)

```python
@pytest.fixture(autouse=True)
def db_reset(db_setup):
    with db.atomic() as transaction:
        yield
        transaction.rollback()
```

Runs **once per test**, automatically. Each test executes inside a Peewee transaction (`db.atomic()`); when the test returns, the transaction is rolled back. Anything you wrote to the database during the test - records, updates, deletes - disappears. The next test sees the same starting state.

Because the fixture is `autouse=True`, you don't list `db_reset` in your test signature unless you want pytest's dependency-ordering rules to make it explicit. The generated test scaffold does name it, mostly as a hint to the reader that this test touches the database:

```python
def test_photo_show(db_reset):
    photo = Photo.create(title="Sunset")
    result = client.get(f"/photos/{photo.id}")
    assert result.status == 200
```

:::note | Why transaction rollback instead of "delete everything after"
Rollback is faster than `DELETE FROM ...` on every table, and it covers cases a manual cleanup wouldn't - rows your code inserted in a callback, foreign keys you didn't think about, sequences whose next value depends on the run. The trade-off is that any code under test that calls `db.atomic()` itself sees a *nested* savepoint, not a top-level transaction. For application code that's almost never a problem; if you're testing something that explicitly commits, see [Tips](#tips-and-common-pitfalls).
:::

### Seed data with `load_fixtures()`

The generated `load_fixtures()` is an empty function. Fill it in when you have data that every test wants - lookup tables, a default admin account, a feature-flag record. The function runs *inside* the session-scope setup, so its rows sit in the base state that every test rolls back to:

```python {title="tests/conftest.py"}
def load_fixtures():
    from myapp.models import Country, Role

    Country.insert_many([
        {"code": "US", "name": "United States"},
        {"code": "GB", "name": "United Kingdom"},
        {"code": "DE", "name": "Germany"},
    ]).execute()

    Role.insert_many([
        {"name": "admin"},
        {"name": "member"},
    ]).execute()
```

For data that varies per test, create it in the test itself (or in a per-test fixture). Tests are isolated, and the rollback fixture means there is no cost to recreating a record in every test that needs it.

----

## Running tests

```bash
$ uv run pytest
```

That's the whole command. `uv run` resolves the project's environment from `pyproject.toml`; `pytest` discovers everything under `tests/` matching the default pattern (`test_*.py` files containing `test_*` functions or `Test*` classes).

:::tip | Always use `uv run pytest`
Running `pytest` directly often works, but it's the version on your `PATH`, with whatever environment shell happens to be active. `uv run pytest` always uses the project's pinned `pytest` and the project's dependencies. The few extra characters save you the "works on my machine" mystery.
:::

### Running a subset

Pytest's selection flags work as you'd expect:

```bash
# A single file
$ uv run pytest tests/test_photos.py

# A single test
$ uv run pytest tests/test_photos.py::test_create_redirects_and_persists

# Every test whose name contains "create"
$ uv run pytest -k create

# Stop at the first failure
$ uv run pytest -x

# Show print() output, even on passing tests
$ uv run pytest -s
```

### Coverage

For coverage, install `pytest-cov` and pass `--cov=`:

```bash
$ uv add --dev pytest-cov
$ uv run pytest --cov=myapp --cov-report=term-missing
```

`--cov-report=term-missing` prints the line numbers that weren't executed in each file, which is far more useful day-to-day than a single percentage. Generated apps target 100% coverage on controllers and models; missing lines almost always point at branches that need a test, not at code that should be deleted.

----

## The `TestClient`: making requests

Every method on `TestClient` returns a `result` object - a `DotDict` with `status`, `body`, `mimetype`, `content_type`, and `headers`. We'll come back to that object after walking through the request side.

### GET, HEAD, OPTIONS

The three "no body" verbs take a URL and optional `params` and `headers`:

```python
result = client.get("/photos")
result = client.get("/photos", params={"page": "2", "sort": "date"})
result = client.head("/photos")
result = client.options("/photos")
```

`params` are appended as a query string. Pass values as strings - the ASGI scope's `query_string` is bytes, and Proper's request layer parses them as text, so anything `int` or `bool` should be stringified at the call site.

`HEAD` returns the same headers as the equivalent `GET` but with an empty body. Don't assert on `result.body` for a `HEAD` request - it's always `""`.

### POST, PUT, PATCH, DELETE, QUERY

The five "with body" verbs additionally accept `body` and `upload_files`:

```python
result = client.post("/photos", body={"title": "Sunset", "published": "true"})
result = client.patch("/photos/1", body={"title": "Sunset, edited"})
result = client.put("/photos/1", body={"title": "Sunset, replaced"})
result = client.delete("/photos/1")
result = client.query("/search", body={"filters": "recent"})
```

`body` accepts four shapes; the client picks an encoding based on the type:

Body type   | Encoded as                          | Content-Type set
----------- | ----------------------------------- | -----------------------------------------
`dict`      | URL-encoded form fields             | `application/x-www-form-urlencoded`
`str`       | UTF-8 bytes, as-is                  | not set - pass it in `headers` if needed
`bytes`     | as-is                               | not set
`BytesIO`   | bytes read from the buffer          | not set

A typical JSON post supplies the body as a string and the content type explicitly:

```python
import json

result = client.post(
    "/api/photos",
    body=json.dumps({"title": "Sunset"}),
    headers={"content-type": "application/json"},
)
```

`QUERY` is the HTTP method introduced in [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-query) - a `GET` that takes a request body. Proper's `TestClient` supports it for completeness; most apps won't use it.

### Custom headers

Pass headers as a plain dict to any method:

```python
result = client.get("/api/users", headers={
    "authorization": "Bearer token123",
    "accept": "application/json",
})
```

The `TestClient` adds two headers on every request automatically:

- `forwarded: for=127.0.0.1;` - so your app sees a sensible client IP.
- `user-agent: TestClient` - so logs and analytics can tell test traffic apart.

If you set either of those in your own `headers` dict, your value wins.

### File uploads

For `multipart/form-data` requests, use the `upload_files` parameter alongside `body`. Each entry is a `(field_name, file_path)` tuple:

```python
result = client.post(
    "/photos",
    body={"title": "Sunset"},
    upload_files=[("image", "tests/fixtures/sunset.jpg")],
)
```

The file is read from disk and added as a multipart part with its `Content-Type` guessed from the extension (via the stdlib `mimetypes` module). Form fields in `body` become text parts of the same multipart message.

Upload multiple files under the same field name to test array-style inputs:

```python
result = client.post(
    "/gallery",
    body={"album": "vacation"},
    upload_files=[
        ("photos", "tests/fixtures/photo1.jpg"),
        ("photos", "tests/fixtures/photo2.jpg"),
    ],
)
```

Two restrictions when `upload_files` is set:

- `body` must be a dict (form fields) or omitted. Mixing a raw string body with file uploads raises `ValueError`.
- Files must exist on disk at the path you pass. There is no in-memory variant - if you need to upload bytes you generated at test time, write them to a temp file first (pytest's `tmp_path` fixture is the usual way).

Keep a `tests/fixtures/` directory under your project for small files you upload often - a one-pixel PNG, a tiny CSV, a short PDF. Don't check in anything large; the suite should fit comfortably in a clone.

----

## The result object

Every method on `TestClient` returns a `DotDict` with these attributes:

| Attribute      | Type   | Description                                       |
|----------------|--------|---------------------------------------------------|
| `status`       | `int`  | HTTP status code (e.g., `200`, `404`, `303`)      |
| `body`         | `str`  | Response body decoded as a string                 |
| `mimetype`     | `str`  | Content type without charset (`"text/html"`)      |
| `content_type` | `str`  | Full `Content-Type` header value (with charset)   |
| `headers`      | dict   | Case-insensitive dict of response headers         |

A representative assertion:

```python
result = client.get("/photos/42")

assert result.status == 200
assert result.mimetype == "text/html"
assert "Sunset" in result.body
assert result.headers["content-type"] == "text/html; charset=utf-8"
```

A few things worth knowing.

### Headers are case-insensitive

`result.headers["Content-Type"]`, `result.headers["content-type"]`, and `result.headers["CONTENT-TYPE"]` all return the same value. That matches how HTTP itself treats header names - the test code shouldn't have to match the server's casing.

For headers that can appear more than once (the classic case is `Set-Cookie`, but `Vary` and `Link` come up too), use `getall()`:

```python
cookies = result.headers.getall("set-cookie")
```

`result.headers["set-cookie"]` returns only the *last* value, which is rarely what you want when multiple cookies are set.

### `body` is already decoded

The response is decoded from whatever charset the server declared (defaulting to UTF-8) before being placed in `result.body`. There is no `.text` vs `.content` distinction - you get a `str`. For binary responses (images, PDFs, downloads), assert on `result.headers["content-type"]` and `len(result.body)`; if you need the raw bytes, you'll have to switch to a different test approach for that endpoint - the `TestClient` is built around the string assumption.

### Redirects are not followed

When a controller redirects, you get the **redirect response**, not the eventual destination:

```python
result = client.post("/photos", body={"title": "New"})
assert result.status == 303
assert result.headers["location"] == "/photos/1"
```

This is deliberate. A test that "follows redirects" silently glues two requests together and turns one HTTP exchange into two - which means a regression in either one looks the same as a regression in the other. Asserting on the redirect itself is cheaper, faster, and more precise. If you want to see what the destination renders, make the next request explicitly:

```python
result = client.post("/photos", body={"title": "New"})
assert result.status == 303

show = client.get(result.headers["location"])
assert "New" in show.body
```

### JSON responses

`result.body` for a JSON endpoint is the raw response string. Parse it with `json.loads` and assert on the structure:

```python
import json

result = client.get("/api/photos/42")
assert result.mimetype == "application/json"

data = json.loads(result.body)
assert data["title"] == "Sunset"
```

Some apps add a small helper - `result.json()` - on a project-local subclass of `TestClient`. The framework keeps the surface minimal so the result object stays a plain dict.

----

## Testing with authentication

If your app uses the [auth addon](/docs/authentication), the `TestClient` has a `sign_in()` helper that authenticates the client for the requests that follow.

### `sign_in()`

`sign_in()` takes a `Session` object - the same kind the auth addon creates when a user logs in - and attaches its signed cookie to the client. Every request the client makes afterwards is authenticated; you don't pass anything back by hand.

```python
from myapp.models import User, Session


def test_dashboard_when_authenticated(client):
    user = User.create(login="testuser", password="password123")
    session = Session.create_for_user(user=user)
    client.sign_in(session)

    result = client.get("/dashboard")
    assert result.status == 200
    assert "Dashboard" in result.body
```

What `sign_in(session)` does is small and direct: it signs the session token and stores it in the client's default headers as the auth cookie. It makes **no HTTP request** and returns nothing. Because the cookie lives on `client.default_headers`, it is sent automatically on every subsequent `client.get(...)`/`client.post(...)` - the client *does* carry it forward, which is exactly what you want for a sequence of authenticated requests in one test. A fresh `TestClient` (such as the one from the `client` fixture) starts with no cookie, so auth state never leaks between tests.

### A signed-in user creating a record

The pattern is the same for any authenticated action - sign in once, then make the request:

```python
def test_create_post_as_authenticated_user(client):
    user = User.create(login="testuser", password="password123")
    client.sign_in(Session.create_for_user(user=user))

    result = client.post(
        "/posts",
        body={"title": "Hello", "body": "World"},
    )
    assert result.status == 303
```

When you find yourself repeating the create-user-then-sign-in dance across many tests, extract a fixture. The auth addon already ships one in `tests/conftest.py` called `signed_client` - a client that is already signed in:

```python {title="tests/conftest.py"}
@pytest.fixture()
def signed_client(client):
    """A test client with a signed-in user."""
    user = User.create(login="testuser", password="password123")
    session = Session.create_for_user(user=user)
    client.sign_in(session)
    return client


# In a test:
def test_dashboard(signed_client):
    result = signed_client.get("/dashboard")
    assert result.status == 200
```

### Signing out

There is no `sign_out()` helper. Signing out in a test just means dropping the auth cookie the client is carrying:

```python
def test_dashboard_requires_auth_after_signout(client):
    user = User.create(login="testuser", password="password123")
    client.sign_in(Session.create_for_user(user=user))

    client.default_headers.pop("cookie", None)   # forget the session

    result = client.get("/dashboard")
    assert result.status == 303   # bounced to /sign-in
```

### Testing unauthenticated access

The first half of every "auth required" test is the same: hit the URL without a cookie, expect a 303 to the sign-in page:

```python
def test_dashboard_requires_auth(client):
    result = client.get("/dashboard")
    assert result.status == 303
    assert "/sign-in" in result.headers["location"]
```

This pairs naturally with the "when authenticated" test above. Together they document both branches of the controller's auth check.

----

## Testing models

Models are tested directly. There is no model-test base class, no fixture that constructs a model in a special way - Peewee works the same in a test as it does in production, and the `db_reset` fixture keeps the database honest.

```python {title="tests/test_user_model.py"}
from myapp.models import User


def test_email_is_normalized_on_save():
    user = User.create(login="Alice", email="ALICE@example.com", password="x")
    assert user.email == "alice@example.com"


def test_full_name_combines_first_and_last():
    user = User.create(login="alice", first_name="Alice", last_name="Smith", password="x")
    assert user.full_name == "Alice Smith"


def test_login_must_be_unique():
    User.create(login="alice", password="x")
    with pytest.raises(IntegrityError):
        User.create(login="alice", password="x")
```

A few patterns that come up often:

- **Test the boundary you care about.** If a method normalises an email address, test that the normalised form is what gets stored - not the path through whatever method called it. The narrower the assertion, the easier it is to read when it fails.
- **Don't test the ORM.** "Calling `.create()` then `.get_by_id()` returns the same record" is a Peewee test, not a yours-to-write test.
- **Concerns are model classes too.** A concern (in `models/concerns/`) is just a subclass of `BaseModel` that isn't registered in `models/__init__.py`. Test the methods it adds by attaching it to any model that uses it - or, if the concern stands alone, by writing a tiny test-only model that includes it.

----

## Testing forms

Forms in Proper use [Formidable](/docs/forms). They are constructed with data (usually `self.params` in a controller), validated, and saved. In a test, you construct them directly:

```python {title="tests/test_photo_form.py"}
from myapp.forms import PhotoForm


def test_valid_form_passes():
    form = PhotoForm({"title": "Sunset", "caption": "Over the bay"})
    assert form.is_valid


def test_missing_title_is_invalid():
    form = PhotoForm({"title": "", "caption": "Anything"})
    assert form.is_invalid
    assert "title" in form.errors


def test_save_returns_cleaned_data():
    form = PhotoForm({"title": "  Sunset  ", "caption": "x"})
    assert form.is_valid

    data = form.save()
    assert data["title"] == "Sunset"   # stripped of whitespace
```

For forms that take an instance (the edit-form pattern), pass it as the second argument:

```python
def test_form_pre_fills_from_instance():
    photo = Photo.create(title="Old")
    form = PhotoForm(None, photo)

    assert form.title.value == "Old"
```

Form tests are unit tests - they don't touch a controller, they don't go through the router, and they don't render HTML. They run fast, they fail with precise messages, and they're the right place to cover every validation branch your form has. The controller test then asserts the high-level "valid form persists, invalid form re-renders" behaviour without re-checking every validator.

----

## Testing emails

The test environment uses `ToMemoryMailer`, which keeps every sent message in `app.mailer.outbox` instead of sending it. Combined with `MemoryHuey` running in immediate mode, that means `EmailMessage.send_later()` puts a message in the outbox *synchronously* - by the time the call returns, the message is there to assert on.

A typical email test:

```python {title="tests/test_password_reset.py"}
from myapp.main import app


def test_reset_request_sends_email(client):
    User.create(login="alice", email="alice@example.com", password="x")

    result = client.post("/password-reset", body={"login": "alice"})
    assert result.status == 303

    assert len(app.mailer.outbox) == 1
    email = app.mailer.outbox[0]
    assert email["Subject"] == "Reset your password"
    assert email["To"] == "alice@example.com"
    assert "reset" in email.get_body(("plain", "html")).get_content().lower()
```

Outbox entries are standard-library `email.message.EmailMessage` objects. Headers are accessed by name (case-insensitive), and bodies through `get_body()` and `get_content()`. The deeper details - the API for each mailer backend, how `Bcc` is handled, what `attach_alternative()` produces - live in the [Sending Emails guide, section on Testing](/docs/emails#testing).

The one thing worth repeating here: **the outbox accumulates across the test**. If your test asserts `len(app.mailer.outbox) == 1`, but an earlier test left a message there, the count will be off. Two ways to handle it:

```python
# Either: reset the outbox in an autouse fixture
@pytest.fixture(autouse=True)
def clear_outbox():
    app.mailer.outbox.clear()
    yield

# Or: assert against the count delta
def test_one_email_was_sent(client):
    before = len(app.mailer.outbox)
    client.post("/some-action")
    assert len(app.mailer.outbox) == before + 1
```

The autouse fixture is the friendlier default. Add it to `tests/conftest.py` if any of your tests assert on outbox length.

----

## Testing background tasks

Background tasks go through Huey. In the test environment, `QUEUE` is configured with `immediate=True`, which makes the queue run every enqueued task **synchronously, in the calling process**. So this:

```python
from myapp.tasks import generate_thumbnails


def test_thumbnail_task_creates_files(tmp_path, db_reset):
    photo = Photo.create(title="x", original=str(tmp_path / "src.jpg"))
    generate_thumbnails(photo.id)

    photo = Photo.get_by_id(photo.id)
    assert photo.thumbnail is not None
```

calls `generate_thumbnails` *like a regular function*. There is no worker, no queue polling, no `await`. The side effects - rows created, files written, emails sent - are there by the time the call returns, ready to assert on.

The same applies to anything that goes *through* the queue indirectly. `EmailMessage.send_later()` enqueues `send_email_task`, which runs immediately, which calls the mailer, which lands a message in `app.mailer.outbox`. Three layers, no `await`, no `sleep()`.

For the deeper testing patterns - asserting on the task's return value, exercising the actual *queue* (serialization round-trip, retries), and switching modes for an integration test - see the [Background Tasks guide](/docs/tasks).

----

## Testing channels (WebSockets)

Channels are tested through `client.websocket()`, which returns an async `WebSocketTestSession`. The session is an `async`-only API because the underlying ASGI machinery is async, so a channel test is a coroutine that you drive with `asyncio.run()`:

```python
import asyncio


def test_chat_channel_broadcasts(client):
    async def scenario():
        ws = client.websocket()
        task = await ws.connect()

        confirm = await ws.subscribe("ChatChannel", room="general")
        assert confirm["type"] == "confirm_subscription"

        await ws.send_action("ChatChannel", "speak", {"message": "hello"})

        msg = await ws.receive()
        assert msg["data"]["message"] == "hello"

        await ws.close()
        await task

    asyncio.run(scenario())
```

The shape is always the same: connect, subscribe, exchange messages, close. The `task` returned by `connect()` is the background coroutine that runs the WebSocket handler - awaiting it after `close()` lets the handler shut down cleanly.

### The session API

| Method                                      | Description                                         |
|---------------------------------------------|-----------------------------------------------------|
| `ws.connect()`                              | Start the WebSocket handler, returns an async task  |
| `ws.subscribe(channel, **params)`           | Subscribe and return the confirmation message       |
| `ws.send_action(channel, action, data)`     | Invoke a channel action                             |
| `ws.unsubscribe(channel, **params)`         | Unsubscribe from a channel                          |
| `ws.receive(timeout=1.0)`                   | Receive the next message (parsed JSON)              |
| `ws.receive_raw(timeout=1.0)`               | Receive the next raw ASGI message                   |
| `ws.client_send(data)`                      | Queue a JSON message to the app                     |
| `ws.client_send_raw(msg)`                   | Queue a raw ASGI message to the app                 |
| `ws.close()`                                | Disconnect the client                               |

`receive()` parses the next outgoing message as JSON. If you need the unparsed ASGI envelope (to inspect the message *type*, for example), `receive_raw()` returns it as a dict. Both methods take a `timeout=` in seconds; if no message arrives in time, `asyncio.TimeoutError` is raised. Default is one second - generous for an in-process test, tight enough that a hung handler fails fast.

### Custom path

By default, `client.websocket()` connects to the `CABLE_PATH` configured on the app (`/cable` if unset). Pass a different path to test a channel mounted somewhere else:

```python
ws = client.websocket("/custom-ws")
```

For everything channels-specific - subscription parameters, broadcasts, the streams API - see the [Channels guide](/docs/channels).

----

## Tips and common pitfalls

A short list of things that have surprised someone at least once.

### Prefer real objects to mocks

Tests use the real database (`:memory:`), the real queue (immediate mode), the real cache (no-op), and the real mailer (in-memory). Resist the urge to reach for `unittest.mock.patch` for these. Mocks drift from the real behaviour; when production breaks because the mock's API differed from the library's, the test that should have caught it didn't. The transactional rollback fixture is what makes "use the real thing" affordable.

### A 303 is the success, not a failure to follow

Said in the result-object section, said again here because the surprise can be costly: if your code does a `redirect_to(...)`, the test sees the **redirect response**. `assert result.status == 200` after a successful create will fail every time - the right assertion is `assert result.status == 303` and, if the destination matters, `assert result.headers["location"] == "/photos/1"`.

### The outbox accumulates

`app.mailer.outbox` lives on the app, which lives across tests. If two tests both end with `assert len(app.mailer.outbox) == 1`, the second one will see two messages and fail. Either add an autouse fixture that calls `app.mailer.outbox.clear()` before each test, or assert against the delta. See the [Testing emails](#testing-emails) section.

### About the `db_reset` fixture

Three things to know about the autouse transactional fixture, in roughly the order you'll meet them.

**The safety check is load-bearing.** The `assert os.getenv("APP_ENV") == "test"` and `assert "test" in db.database or "memory" in db.database` in `db_setup` are not decoration - they're the line standing between you and someone who accidentally ran pytest with `APP_ENV=production` in their shell. The cost of an assertion firing in the wrong place is zero; the cost of dropping a production schema is unbounded. Leave them.

**Explicit naming is a hint, not a requirement.** Because `db_reset` has `autouse=True`, every test runs inside the rollback transaction whether it lists the fixture or not. The generator scaffolds it explicitly (`def test_x(db_reset):`) as a signal to the reader that the test touches the database. Both styles work; pick one and be consistent.

**When you genuinely need a commit.** If you're testing code that itself calls `db.atomic()` and expects to commit - rare in application code, common when testing migrations or low-level utilities - the outer rollback turns the inner transaction into a savepoint. The cleanest escape is a marker that opts out of the fixture:

```python
@pytest.fixture(autouse=True)
def db_reset(db_setup, request):
    if "no_db_reset" in request.keywords:
        yield
        return
    with db.atomic() as transaction:
        yield
        transaction.rollback()


@pytest.mark.no_db_reset
def test_migration_actually_commits():
    ...
```

Manage cleanup yourself in the marked test - drop and recreate the affected tables, or use a separate connection.

### Caching is off in tests, on purpose

`NoCache` in the test environment means `app.cache.get(...)` never returns a value. If you have a test that verifies a *positive* hit on the cache, switch to `SqliteCache` with `":memory:"` for that test only - either by overriding `CACHE` in a fixture, or by writing a tiny stand-alone test that wires up its own app. Most tests want caching off; the targeted exceptions are clearer when they say so.

### Don't `sleep()` waiting for background work

In immediate mode, "background work" finishes before the line that enqueued it returns. If a test ever needs `time.sleep()` to "let the worker catch up," the test is almost certainly in the wrong mode - check that `QUEUE` is the in-memory variant and that the task is being enqueued through the queue, not via a real Huey consumer.

### Keep fixture files small

Anything in `tests/fixtures/` ends up in every clone of your repository. A 5 MB JPEG that exists to test "an image uploads" makes the repo 5 MB heavier forever. A one-pixel PNG works just as well; the upload pipeline doesn't care what the image *is*.

----

## What's next

Testing touches almost every part of Proper. A few places to go from here:

- [Sending Emails](/docs/emails#testing) - the canonical reference for `ToMemoryMailer`, outbox introspection, and testing email classes in isolation.
- [Background Tasks](/docs/tasks) - how immediate mode works under the hood, when to switch to a real consumer for an integration test, and the deeper Huey APIs.
- [Channels](/docs/channels) - the framework side of the WebSocket protocol the test session exercises.
- [Authentication](/docs/authentication) - how the `Session` model works and how `current.user` is resolved on each request.
- [Controllers Advanced Topics](/docs/controllers_advanced) - error handlers, conditional GETs, and the controller behaviours that round out a complete test suite.
