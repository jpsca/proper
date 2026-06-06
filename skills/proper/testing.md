---
title: Testing
description: TestClient setup, making requests, file uploads, WebSocket testing, auth helpers
last_verified: 2026-04-02
---

# Testing

Proper includes a `TestClient` that drives your app through the full ASGI stack — the same pipeline, middleware, database connections, and session handling that run in production. No mocking of internals is needed.

## Table of Contents

- [Setup](#setup)
- [Making Requests](#making-requests)
- [File Uploads](#file-uploads)
- [The Result Object](#the-result-object)
- [Testing WebSockets](#testing-websockets)
- [Database Setup for Tests](#database-setup-for-tests)
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

Every call to `client.get(...)`, `client.post(...)`, etc. creates a fresh ASGI scope, runs the full request pipeline synchronously, and returns a result object.


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
| `headers`      | `dict` | Case-insensitive dict of response headers         |

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

### Testing JSON Responses

```python
import json

result = client.get("/api/photos/42")
assert result.mimetype == "application/json"
data = json.loads(result.body)
assert data["title"] == "Sunset"
```


## Testing WebSockets

The `TestClient` includes an async WebSocket helper for testing channels:

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
    await ws.send_action("ChatChannel", "speak", {"message": "hello"})

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
| `ws.connect()`                              | Start the WebSocket handler, returns an async task  |
| `ws.subscribe(channel, **params)`           | Subscribe and return the confirmation message       |
| `ws.send_action(channel, action, data)`     | Invoke a channel action                             |
| `ws.unsubscribe(channel, **params)`         | Unsubscribe from a channel                          |
| `ws.receive(timeout=1.0)`                   | Receive the next message (parsed JSON)              |
| `ws.receive_raw(timeout=1.0)`               | Receive the next raw ASGI message                   |
| `ws.client_send(data)`                      | Queue a JSON message to the app                     |
| `ws.client_send_raw(msg)`                   | Queue a raw ASGI message to the app                 |
| `ws.close()`                                | Disconnect the client                               |

### Custom WebSocket Path

By default, `client.websocket()` connects to the configured `CABLE_PATH` (default: `/cable`). You can override it:

```python
ws = client.websocket("/custom-ws")
```


## Database Setup for Tests

The generated `tests/conftest.py` sets up automatic transaction rollback per test, so each test runs in isolation without persisting data:

```python {title="tests/conftest.py"}
import pytest

from myapp.models import db
from myapp.models.base import BaseModel


@pytest.fixture(scope="session")
def db_setup():
    assert "_test" in db.database or db.database == ":memory:"
    models = BaseModel.__subclasses__()
    db.drop_tables(models)
    db.create_tables(models, safe=True)
    load_fixtures()
    yield
    db.drop_tables(models)


def load_fixtures():
    pass


@pytest.fixture(autouse=True)
def db_reset(db_setup):
    with db.atomic() as transaction:
        yield
        transaction.rollback()
```

Key features:

- **Safety check** — asserts the database name contains `_test` or is `:memory:` to prevent accidentally wiping a real database.
- **Auto-discovery** — finds all models via `BaseModel.__subclasses__()`.
- **Transaction rollback** — every test runs inside a transaction that is rolled back, ensuring tests are isolated and fast.
- **Fixtures** — add seed data in `load_fixtures()`, loaded once per session.

Configure a test database in `config/storage.py`:

```python
if env == "test":
    DATABASES["main"] = {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": ":memory:",
    }
```


## Testing with Authentication

The `TestClient` provides `sign_in()` and `sign_out()` methods for authentication. Since the client does not persist cookies between requests, `sign_in()` returns the auth cookie string that you pass to subsequent requests via the `Cookie` header.

### Signing In

```python
from proper import TestClient
from myapp.main import app
from myapp.models import User

client = TestClient(app)


def test_dashboard_requires_auth():
    result = client.get("/dashboard")
    assert result.status == 303  # redirected to sign-in

def test_dashboard_when_authenticated():
    User.create(login="testuser", password="password123")
    cookie = client.sign_in("testuser", "password123")

    result = client.get("/dashboard", headers={"Cookie": cookie})
    assert result.status == 200
    assert "Dashboard" in result.body
```

`client.sign_in(login, password)` POSTs to `/sign-in`, asserts a 303 redirect, and returns the `_auth` cookie string. The defaults are `login="testuser"` and `password="password123"`.

### Creating Records as a Signed-In User

```python
def test_create_post_as_authenticated_user():
    User.create(login="testuser", password="password123")
    cookie = client.sign_in("testuser", "password123")

    result = client.post(
        "/posts",
        body={"title": "Hello", "body": "World"},
        headers={"Cookie": cookie},
    )
    assert result.status == 303
```

### Testing Sign-Out

```python
def test_sign_out_clears_session():
    User.create(login="testuser", password="password123")
    cookie = client.sign_in("testuser", "password123")

    client.sign_out()

    # Old cookie no longer works
    result = client.get("/dashboard", headers={"Cookie": cookie})
    assert result.status == 303  # redirected to sign-in
```


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
- **Disable caching in tests** — use `NoCache` in test config to avoid cached state between tests.
- **TestClient does not follow redirects** — assert on `result.status == 303` and check the `Location` header. Don't expect a 200 after a create/update/delete.
