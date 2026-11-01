---
title: Testing
description: TestClient setup, making requests, file uploads, WebSocket testing, auth helpers
last_verified: 2026-10-31
sources:
  - src/proper/test_client.py
  - blueprint/tests
  - src/proper/_blueprints/addon_auth/tests
  - blueprint/[[app_name]]/config
---

# Testing

Proper includes a `TestClient` that drives your app through the full request pipeline — the same routing, callbacks, database connections, and session handling that run in production, without a server. No mocking of internals is needed.

## Table of Contents

- [Setup](#setup)
- [Making Requests](#making-requests)
- [File Uploads](#file-uploads)
- [The Result Object](#the-result-object)
- [Testing WebSockets](#testing-websockets)
- [Database Setup for Tests](#database-setup-for-tests)
- [Testing Models](#testing-models)
- [Testing with Authentication](#testing-with-authentication)
- [Example: Full CRUD Test](#example-full-crud-test)
- [Tips](#tips)


## Setup

Import the `TestClient` and pass it your app instance:

```python
from proper import TestClient
from myapp.main import app

client = TestClient(app)
```

Every call to `client.get(...)`, `client.post(...)`, etc. builds a request the way the server would, runs the full request pipeline synchronously, and returns a result object.

The generated `tests/conftest.py` provides a `client` fixture (a new `TestClient(app)` per test); the generated tests take it as an argument instead of building one at module level, as the examples below do for brevity.


## Making Requests

### GET and HEAD

```python
result = client.get("/photos")
assert result.status == 200
assert "Photos" in result.body

result = client.head("/photos")
assert result.status == 200
assert result.body == ""   # HEAD strips the body
```

Pass query string parameters with `params`:

```python
result = client.get("/photos", params={"page": "2", "sort": "date"})
```

The path is percent-decoded before routing, as the server does: `client.get(app.url_for("Tag.show", tag="a b"))` requests `/tags/a%20b` and the controller gets `"a b"`.

Requests come from `client.remote_ip` (`127.0.0.1`, a default trusted proxy), so `X-Forwarded-For` and `X-Forwarded-Proto` sent in a test are used; set `client.remote_ip = "203.0.113.5"` to test a client that connects directly (they are ignored then). `make_test_request()` without `client=` has no peer address, which counts as trusted.

### POST, PUT, PATCH, DELETE

These methods accept a `body` parameter. When `body` is a dict, it is encoded as `application/x-www-form-urlencoded`:

```python
result = client.post("/photos", body={"title": "Sunset", "published": "true"})
assert result.status == 303   # redirect after create
```

You can also send raw strings or bytes:

```python
result = client.post("/api/data", body='{"key": "value"}', headers={
    "content-type": "application/json",
})
```

All methods that accept a body: `post`, `put`, `patch`, `delete`, `query`.

### OPTIONS

```python
result = client.options("/photos")
```

### QUERY

The `QUERY` method is like GET but with a body:

```python
result = client.query("/search", body={"filters": "recent"})
```

### Custom Headers

Pass headers as a dict to any request method:

```python
result = client.get("/api/users", headers={
    "authorization": "Bearer token123",
    "accept": "application/json",
})
```

Headers for every request go to the constructor, `TestClient(app, headers={"authorization": "Bearer token123"})`, or into `client.default_headers` later (keys lowercased). A header given to a request overrides them. `client.sign_in()` writes the auth cookie there, and the WebSocket handshake sends them too.


## File Uploads

Use the `upload_files` parameter to upload files. Each entry is a tuple of `(field_name, file_path)`:

```python
result = client.post(
    "/photos",
    body={"title": "Sunset"},
    upload_files=[("image", "tests/fixtures/sunset.jpg")],
)
```

The file is read from disk and encoded as `multipart/form-data`. The content type is auto-detected from the file extension.

Multiple files can be uploaded at once:

```python
result = client.post(
    "/gallery",
    upload_files=[
        ("photos", "tests/fixtures/photo1.jpg"),
        ("photos", "tests/fixtures/photo2.jpg"),
    ],
)
```

When using `upload_files`, the `body` parameter must be a dict (form fields) or omitted.


## The Result Object

Every request returns a `DotDict` with the following attributes:

| Attribute      | Type   | Description                                       |
|----------------|--------|---------------------------------------------------|
| `status`       | `int`  | HTTP status code (e.g., `200`, `404`, `303`)      |
| `body`         | `str`  | Response body decoded as a string                 |
| `mimetype`     | `str`  | Content type without charset (e.g. `"text/html"`) |
| `content_type` | `str`  | Full Content-Type header value                    |
| `headers`      | `CIMultiDict` | Case-insensitive, keeps repeated headers: `result.headers.getall("set-cookie")` |

```python
result = client.get("/photos/42")

assert result.status == 200
assert result.mimetype == "text/html"
assert "sunset" in result.body.lower()
assert result.headers["content-type"] == "text/html; charset=utf-8"
```

### Testing Redirects

Redirects are not followed. You get the redirect response directly:

```python
result = client.post("/photos", body={"title": "New"})
assert result.status == 303
assert result.headers["location"] == "/photos/1"
```

### Errors of the App Are Raised

An exception of the app that ends in a server error is raised in the test, with its real traceback, instead of being answered with a `500` page. An `HTTPError` (like `NotFound`), or any exception with a `status`, is always answered, never raised, and so is an error that an error handler answers with a status under 500.

```python
with pytest.raises(ValueError):
    client.get("/explode")
```

To test the error pages themselves, turn it off: `TestClient(app, raise_server_errors=False)`, or `client.raise_server_errors = False`.

### Testing JSON Responses

```python
import json

result = client.get("/api/photos/42")
assert result.mimetype == "application/json"
data = json.loads(result.body)
assert data["title"] == "Sunset"
```


## Testing WebSockets

The `TestClient` includes an async WebSocket helper for testing channels. The app's cable (`Cable`) serves the session from memory, with no port; with an app that has no channels (`CABLE = {}`), `connect()` raises `RuntimeError`.

```python
import asyncio
from proper import TestClient

client = TestClient(app)

async def test_chat():
    ws = client.websocket()
    task = await ws.connect()

    # Subscribe to a channel
    confirm = await ws.subscribe("ChatChannel", room="general")
    assert confirm["type"] == "confirm_subscription"

    # Send an action
    await ws.send_action("ChatChannel", "speak", {"message": "hello"}, room="general")

    # Receive the broadcast
    msg = await ws.receive()
    assert msg["data"]["message"] == "hello"

    # Clean up
    await ws.close()
    await task

asyncio.run(test_chat())
```

### WebSocket Methods

| Method                                      | Description                                         |
|---------------------------------------------|-----------------------------------------------------|
| `client.websocket(path=None)`               | The session; `path` defaults to `CABLE_PATH` and may carry a query string |
| `ws.connect()`                              | Open the connection, returns an async task          |
| `ws.subscribe(channel, positions=None, **params)` | Subscribe and return the first frame back (normally the confirmation; see [channels.md](channels.md#testing)) |
| `ws.send_action(channel, action, data=None, id=None, **params)` | Invoke a channel action, without waiting for a reply |
| `ws.perform(channel, action, data=None, **params)` | Invoke an action with an `id` and return its reply (`status` `ok` or `error`), skipping the frames before it |
| `ws.unsubscribe(channel, **params)`         | Unsubscribe from a channel                          |
| `ws.receive(timeout=1.0)`                   | Receive the next message (parsed JSON)              |
| `ws.receive_raw(timeout=1.0)`               | Receive the next raw event: `{"type": "accept"}`, a frame, or a close |
| `ws.client_send(data)`                      | Queue a JSON message to the app                     |
| `ws.client_send_text(text)`                 | Queue a raw text frame to the app                   |
| `ws.close()`                                | Disconnect the client                               |


## Database Setup for Tests

The generated `tests/conftest.py` sets up automatic transaction rollback per test, so each test runs in isolation without persisting data:

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

    # Hold a connection open on the test thread for the whole session: it keeps
    # a shared-cache in-memory DB alive, and lets a server backend configured
    # with autoconnect=False (e.g. Postgres) run the queries below.
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
    # Roll it back for fast, backend-agnostic isolation.
    with db.atomic() as transaction:
        yield
        transaction.rollback()


def load_fixtures():
    pass
```

Key features:

- **`client` fixture** — a `TestClient(app)` per test.
- **Safety check** — asserts `APP_ENV` is `test` and the database name contains `test` or `memory`, to prevent accidentally wiping a real database.
- **Auto-discovery** — finds all models via `BaseModel.__subclasses__()`.
- **Transaction rollback** — every test runs inside a transaction that is rolled back, ensuring tests are isolated and fast.
- **Fixtures** — add seed data in `load_fixtures()`, loaded once per session.

The generated `config/storage.py` already configures the test environment: an in-memory database, tasks that run inline when enqueued, and no cache:

```python
if env == "test":
    DATABASES["main"] = {
        "type": "peewee.SqliteDatabase",
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

The generated `config/main.py` sets `MAILER = "memory"` in test: emails go to `app.mailer.outbox`, a list of the rendered messages (see [emails.md](emails.md#tomemorymailer-testing)).


## Testing Models

Write model tests against real database operations, not mocks:

```python
def test_create_photo():
    photo = Photo.create(title="Sunset", published=True)
    assert photo.id is not None
    assert photo.title == "Sunset"


def test_query_published_photos():
    Photo.create(title="Sunset", published=True)
    Photo.create(title="Draft", published=False)

    published = Photo.select().where(Photo.published == True)
    assert published.count() == 1
    assert published[0].title == "Sunset"
```


## Testing with Authentication

`client.sign_in(session)` takes a `Session` record and writes the signed `_auth` cookie into `client.default_headers`, so every following request of that client, and its WebSocket handshake, is authenticated. It makes no request and returns nothing. The auth addon appends two fixtures to `tests/conftest.py`:

```python {title="tests/conftest.py (appended by the auth addon)"}
from myapp.models import User, Session


@pytest.fixture()
def sign_in_as(client):
    def _sign_in_as(user):
        """Signs in as the given user using the provided test client."""
        session = Session.create_for_user(user=user)
        client.sign_in(session)
    return _sign_in_as


@pytest.fixture()
def signed_client(client, sign_in_as):
    """A test client with a signed-in user."""
    user = User.create(login="testuser", password="password123")
    sign_in_as(user)
    return client
```

### Signing In

```python
from myapp.models import User


def test_dashboard_requires_auth(client):
    result = client.get("/dashboard")
    assert result.status == 303  # redirected to sign-in


def test_dashboard_when_authenticated(signed_client):
    result = signed_client.get("/dashboard")
    assert result.status == 200
    assert "Dashboard" in result.body


def test_dashboard_as_a_given_user(client, sign_in_as):
    user = User.create(login="bob", password="password123")
    sign_in_as(user)

    result = client.get("/dashboard")
    assert result.status == 200
```

### Creating Records as a Signed-In User

```python
def test_create_post_as_authenticated_user(signed_client):
    result = signed_client.post(
        "/posts",
        body={"title": "Hello", "body": "World"},
    )
    assert result.status == 303
```

### Testing Sign-Out

There is no `sign_out()`: sign out through the app, as a user would. The session row is deleted, so the cookie the client still sends no longer matches one.

```python
def test_sign_out_clears_session(signed_client):
    result = signed_client.delete(app.url_for("Session.delete"))
    assert result.status == 303

    # The cookie is still sent, but its session is gone
    result = signed_client.get("/dashboard")
    assert result.status == 303  # redirected to sign-in
```

To drop the cookie itself: `del client.default_headers["cookie"]`.


## Example: Full CRUD Test

```python {title="tests/test_photos.py"}
from proper import TestClient
from myapp.main import app
from myapp.models import Photo


client = TestClient(app)


def test_index_lists_photos():
    Photo.create(title="Sunset")
    Photo.create(title="Sunrise")

    result = client.get("/photos")
    assert result.status == 200
    assert "Sunset" in result.body
    assert "Sunrise" in result.body


def test_show_displays_photo():
    photo = Photo.create(title="Sunset")
    result = client.get(f"/photos/{photo.id}")
    assert result.status == 200
    assert "Sunset" in result.body


def test_show_returns_404_for_missing_photo():
    result = client.get("/photos/99999")
    assert result.status == 404


def test_create_redirects_on_success():
    result = client.post("/photos", body={"title": "New Photo"})
    assert result.status == 303
    assert Photo.select().where(Photo.title == "New Photo").count() == 1


def test_create_returns_422_on_invalid_data():
    result = client.post("/photos", body={"title": ""})
    assert result.status == 422


def test_update_changes_the_record():
    photo = Photo.create(title="Old Title")
    result = client.patch(f"/photos/{photo.id}", body={"title": "New Title"})
    assert result.status == 303
    photo = Photo.get_by_id(photo.id)
    assert photo.title == "New Title"


def test_delete_removes_the_record():
    photo = Photo.create(title="To Delete")
    result = client.delete(f"/photos/{photo.id}")
    assert result.status == 303
    assert Photo.get_or_none(photo.id) is None
```


## Tips

- **Run tests with**: `uv run pytest tests/`
- **Check coverage**: `uv run pytest --cov=myapp --cov-report=term-missing tests/`
- **Use real objects** — test against real database operations, not mocks. The transaction rollback fixture keeps tests fast and isolated.
- **Test the full stack** — the `TestClient` exercises the same middleware, pipeline, session handling, and error handlers as production. If it works in the test, it works in production.
- **No cache in tests** — the generated `config/storage.py` already uses `NoCache` in test, so nothing is cached between tests.
- **TestClient does not follow redirects** — assert on `result.status == 303` and check the `Location` header. Don't expect a 200 after a create/update/delete.
