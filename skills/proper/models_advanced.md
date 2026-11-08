---
title: Model Mixins, Scopes and Tokens
description: Model concerns (RussianDollCached, your own mixins), chainable `@scope` queries, and signed tokens for a record (`generate_token_for` / `resolve_token_for`)
last_verified: 2026-11-07
sources:
  - src/proper/models
---

# Model Mixins, Scopes and Tokens

Reusable behavior on top of the models in [models.md](models.md).

## Table of Contents

- [Model Concerns (Mixins)](#model-concerns-mixins)
- [Scopes](#scopes)
- [Token Generation](#token-generation)


## Model Concerns (Mixins)

Mixins let you share fields and behavior across models. They also inherit from `BaseModel`:

### RussianDollCached

The one concern the generated app ships (`models/concerns/russian_doll_cached.py`). `BaseModel` already has `created_at`; this concern adds `updated_at`, bumps it on every `save()` and `Model.update()`, and can propagate the bump to parent records so nested cached fragments invalidate ([caching.md](caching.md#russian-doll-caching)):

```python
from .base import BaseModel
from .concerns.russian_doll_cached import RussianDollCached


class Comment(RussianDollCached, BaseModel):
    post = pw.ForeignKeyField(Post, backref="comments")
    body = pw.TextField()

    touches = ("post",)   # saving or deleting a comment bumps post.updated_at
```

It provides:

- `updated_at` - `DateTimeField(default=utcnow, null=True)`, set on `save()` and `update()`
- `touches` - names of foreign keys whose records get `touch()`ed on save and delete; each of those models must be `RussianDollCached` too (or define `touch()`), otherwise it is skipped silently
- `touch()` - bump this record's `updated_at` and propagate through `touches`

`{% cache(obj) %}` and `response.fresh_when(obj)` need `updated_at`, so use this concern on the models you cache.

### Writing Your Own Mixins

Create a file in `models/concerns/` and inherit from `BaseModel`:

```python
# models/concerns/publishable.py
import peewee as pw

from ..base import BaseModel, utcnow


class Publishable(BaseModel):
    published = pw.BooleanField(default=False)
    published_at = pw.DateTimeField(null=True)

    def publish(self):
        self.published = True
        self.published_at = utcnow()
        self.save(only=[self.__class__.published, self.__class__.published_at])

    def unpublish(self):
        self.published = False
        self.published_at = None
        self.save(only=[self.__class__.published, self.__class__.published_at])
```

Then mix it into your model:

```python
class Post(Publishable, BaseModel):
    title = pw.CharField()
    body = pw.TextField()
```


## Scopes

Scopes are reusable query fragments you can chain onto `select()`. They work like Rails scopes — define them once on the model, then mix and match freely.

### Defining Scopes

Import `scope` from `proper` (it's already exported in `base.py`) and decorate class methods. The first argument is the model class and the second is the query:

```python
import peewee as pw

from .base import BaseModel, scope


class Article(BaseModel):
    title = pw.CharField()
    status = pw.CharField(default="draft")
    views = pw.IntegerField(default=0)
    category = pw.CharField(default="general")
    created_at = pw.DateTimeField()

    @scope
    def published(cls, query):
        return query.where(cls.status == "published")

    @scope
    def popular(cls, query, min_views=1000):
        return query.where(cls.views >= min_views)

    @scope
    def in_category(cls, query, cat):
        return query.where(cls.category == cat)

    @scope
    def recent(cls, query):
        return query.order_by(cls.created_at.desc())

    @scope
    def top(cls, query, n=10):
        return query.order_by(cls.views.desc()).limit(n)
```

### Using Scopes

Chain scopes after `.select()` — they compose freely with each other and with native Peewee methods:

```python
# Chain multiple scopes
articles = Article.select().published().popular(500).in_category("tech").recent()

# Mix scopes with native Peewee methods
articles = (Article
    .select()
    .published()
    .where(Article.title.contains("Python"))
    .paginate(1, 20))

# Scopes work across joins
comments = (Comment
    .select()
    .approved_only()
    .recent()
    .join(Article)
    .where(Article.category == "tech"))

# Reuse a base query
base = Article.select().published().recent()
tech    = base.in_category("tech").top(5)
science = base.in_category("science").top(5)
```

Scopes are preserved through `where()`, `order_by()`, `join()`, `switch()`, `paginate()`, `limit()`, `offset()`, and all other query-building methods. Methods like `count()`, `exists()`, or iterating the query execute normally.

### BaseModel Setup

The generated `BaseModel` already inherits from `ProperModel`, so scopes work on all your models out of the box:

```python
# models/base.py
import typing as t
from datetime import datetime, timezone

import peewee as pw

from proper import ProperModel, scope  # noqa
from ..main import app


db = app.db["main"]


def utcnow() -> datetime:
    """The naive UTC datetime peewee's `utcnow` returns, with a type."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _MainDatabase:
    database = db


class BaseModel(ProperModel):
    Meta: t.Any = _MainDatabase

    created_at = pw.DateTimeField(default=utcnow)
```

If a model has no `@scope` methods, it behaves exactly like a regular Peewee model with zero overhead.


## Token Generation

Every model that inherits from `ProperModel` (via `BaseModel`) can generate signed, URL-safe tokens and resolve them back into model instances. This is useful for password resets, email verification links, invitation tokens, file access URLs, or any feature that needs a tamper-proof reference to a record.

There are two levels of API: a **named token** API (recommended) and a **low-level** API.


### Named Tokens (generate_token_for / resolve_token_for)

Named tokens are the recommended approach, inspired by Rails' `generates_token_for`. You define a `generate_token_for_NAME` method on your model that returns a fingerprint value. The name is used as the token's salt, so different token purposes are completely isolated.

#### Defining a named token

Add a method named `generate_token_for_NAME` to your model. It takes no arguments (beyond `self`) and returns a JSON-serializable value that changes when the token should be invalidated:

```python
class User(Authenticable, BaseModel):
    def generate_token_for_password_reset(self):
        # Token becomes invalid when the password changes
        return (self.password or "")[-20::2]

    def generate_token_for_email_verification(self):
        # Token becomes invalid when the email changes
        return self.email
```

#### Generating

```python
token = user.generate_token_for("password_reset")
# => "eyJpZCI6IjQyIiwiZnAi..."
```

#### Resolving

```python
user = User.resolve_token_for("password_reset", token, max_age=3 * HOURS)
# => User instance, or None
```

Returns `None` if:

- The token signature is invalid (tampered)
- The token has expired (older than `max_age`)
- The record no longer exists
- The fingerprint doesn't match (record changed since token was generated)

The default `max_age` is 15 minutes. Named tokens are always timed: `resolve_token_for` has no `timed=False` path, so use the general API below for a token that never expires.

#### Full example: email verification

```python
class User(BaseModel):
    email = pw.CharField(unique=True)
    email_verified_at = pw.DateTimeField(null=True)

    def generate_token_for_email_verification(self):
        return self.email

    def verify_email(self):
        self.email_verified_at = pw.utcnow()
        self.save(only=[User.email_verified_at])


# Generate a verification link
token = user.generate_token_for("email_verification")
url = app.url_for("EmailVerification.edit", token=token, _full=True)

# Later, when the user clicks the link
user = User.resolve_token_for("email_verification", token, max_age=24 * HOURS)
if user:
    user.verify_email()
```


### General API (generate_token / resolve_token)

For cases where you don't need a fingerprint or want to pass an explicit fingerprint callable:

```python
# Generate a simple token (no fingerprint, expiration only)
token = record.generate_token()

# Generate with an explicit fingerprint function
token = user.generate_token(lambda u: u.email, salt="my-purpose")

# Resolve a simple token
record = MyModel.resolve_token(token, max_age=24 * HOURS)

# Resolve with the same fingerprint function
user = User.resolve_token(token, lambda u: u.email, max_age=24 * HOURS, salt="my-purpose")
```

The `fingerprint` argument is a callable that receives the model instance and returns a JSON-serializable value. It defaults to `lambda x: None` (no fingerprint check). The `salt` defaults to the model class name.

Tokens are timed by default: each call gives a different token, and `resolve_token` can enforce `max_age`. Pass `timed=False` for a token without a timestamp: it is identical on every call for the same record, fingerprint and salt, and it can never expire. Since it can't prove its age, it only resolves with `max_age=None`. Use it for stable, cacheable URLs (this is what `attachment.url(stable=True)` does), never for anything that should expire, like password resets.

```python
token = record.generate_token(salt="share", timed=False)   # same value every time
record = MyModel.resolve_token(token, salt="share", max_age=None)
```
