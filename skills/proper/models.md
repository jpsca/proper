---
title: Models
description: Peewee ORM models: defining, field types, relationships, querying, Meta options, custom methods, BaseModel
last_verified: 2026-11-07
sources:
  - src/proper/models
  - src/proper/_blueprints/model
  - blueprint/[[app_name]]/models
---

# Models

Proper uses [Peewee ORM](https://docs.peewee-orm.com) for database access. All models inherit from `BaseModel`, which is configured to use your application's database. Peewee is used directly - there is no abstraction layer on top of it.

Mixins, scopes and signed tokens are in [models_advanced.md](models_advanced.md). Database configuration, migrations and seeds are in [migrations.md](migrations.md). The `proper g model` syntax is in [generators.md](generators.md).

## Table of Contents

- [Defining Models](#defining-models)
- [Prefer adding methods to models](#prefer-adding-methods-to-models)
- [Field Types](#field-types)
- [Relationships](#relationships)
- [Querying](#querying)
- [Meta Class Options](#meta-class-options)
- [Custom Model Methods](#custom-model-methods)
- [BaseModel](#basemodel)
- [Integration with Controllers and Forms](#integration-with-controllers-and-forms)


## Defining Models

Models live in the `models/` directory. Each model is a Python class that inherits from `BaseModel`:

```python
import peewee as pw

from .base import BaseModel


class Photo(BaseModel):
    title = pw.CharField()
    description = pw.TextField(default="")
    published = pw.BooleanField(default=False)
    views = pw.IntegerField(default=0)
```

Peewee automatically adds an `id` auto-incrementing primary key to every model unless you explicitly define one.

Always import Peewee as `import peewee as pw`, not `from peewee import ...`.


### Registering Models for Migrations

**Every model must be imported in `models/__init__.py`** for migration detection to work. If you forget this step, `proper db create` won't see your model changes:

```python
# models/__init__.py
"""
Import here all the models you want to be detected for migrations.
You can also do `from .your_model import *  #noqa` here
and, in your model file, use `__all__` to define what to import

Do not import `BaseModel` or any concern/mixin here.
"""
from .base import db  # noqa
from .photo import Photo  # noqa
from .comment import Comment  # noqa
```

The model generator (`proper g model`) handles this import automatically.


## Prefer adding methods to models

For operations over models data, prefer adding methods to the model to do it.

**DO NOT**
```python
    def show(self):
        # ...
        user.email_verified_at = pw.utcnow()
        user.save()
        # ...
```

**DO**
```python
class User(BaseModel):
    def verify(self):
        self.email_verified_at = pw.utcnow()
        self.save()

    def show(self):
        # ...
        user.verify()
        # ...
```


## Field Types

Peewee provides a full set of field types. Here are the most commonly used ones:

| Field                  | Python Type        | SQL Type            |
|------------------------|--------------------|---------------------|
| `pw.CharField()`      | `str`              | VARCHAR             |
| `pw.TextField()`      | `str`              | TEXT                |
| `pw.IntegerField()`   | `int`              | INTEGER             |
| `pw.BigIntegerField()` | `int`             | BIGINT              |
| `pw.FloatField()`     | `float`            | REAL                |
| `pw.DecimalField()`   | `Decimal`          | DECIMAL             |
| `pw.BooleanField()`   | `bool`             | BOOLEAN             |
| `pw.DateTimeField()`  | `datetime`         | DATETIME            |
| `pw.DateField()`      | `date`             | DATE                |
| `pw.TimeField()`      | `time`             | TIME                |
| `pw.UUIDField()`      | `UUID`             | UUID / VARCHAR      |
| `pw.BlobField()`      | `bytes`            | BLOB                |
| `pw.IPField()`        | `str`              | BIGINT              |

### Common Field Options

Every field accepts these options:

```python
title = pw.CharField(
    max_length=255,       # Maximum length (CharField only)
    null=True,            # Allow NULL values (default: False)
    default="Untitled",   # Default value (can be a callable)
    unique=True,          # Add a unique constraint
    index=True,           # Create an index on this column
    help_text="...",      # Documentation (not used in SQL)
)
```

### JSONField

Use Peewee's `pw.JSONField` for JSON columns. `Model.field["key"]` builds a JSON path for queries:

```python
class Photo(BaseModel):
    title = pw.CharField()
    metadata = pw.JSONField(null=True)


Photo.create(title="Sunset", metadata={"camera": "Canon EOS R5"})
Photo.select().where(Photo.metadata["camera"] == "Canon EOS R5")
```

`from proper import JSONField` exists only for backwards compatibility with the data stored by older versions (it encoded dates as `"__dt__<iso>"` strings). Don't use it in new code.


## Relationships

### Foreign Keys

Use `pw.ForeignKeyField` to define a many-to-one relationship. The `backref` parameter creates a reverse accessor on the related model:

```python
class Comment(BaseModel):
    body = pw.TextField()
    photo = pw.ForeignKeyField(Photo, backref="comments", on_delete="CASCADE")
```

This gives you:

```python
# Access the photo from a comment
comment.photo

# Access all comments from a photo
photo.comments   # SelectQuery that you can iterate, filter, etc.
```

#### on_delete Options

The `on_delete` parameter controls what happens when the referenced record is deleted:

| Value          | Behavior                                      |
|----------------|-----------------------------------------------|
| `"CASCADE"`    | Delete the child records too                  |
| `"SET NULL"`   | Set the foreign key to NULL (requires `null=True`) |
| `"RESTRICT"`   | Prevent deletion if children exist            |
| (not set)      | No clause; the database decides (`NO ACTION`, like `RESTRICT` on most engines) |

#### Self-Referencing Foreign Keys

A model can reference itself. This is useful for tree structures or parent-child relationships:

```python
class Category(BaseModel):
    name = pw.CharField()
    parent = pw.ForeignKeyField("self", backref="children", null=True)
```

### Many-to-Many

Peewee does not have a built-in many-to-many field. Instead, create a through (join) table:

```python
class Tag(BaseModel):
    name = pw.CharField(unique=True)


class PhotoTag(BaseModel):
    photo = pw.ForeignKeyField(Photo, backref="photo_tags", on_delete="CASCADE")
    tag = pw.ForeignKeyField(Tag, backref="tag_photos", on_delete="CASCADE")

    class Meta:
        indexes = (
            (("photo", "tag"), True),  # Unique together
        )
```

Query across the relationship:

```python
# All tags for a photo
tags = (Tag
    .select()
    .join(PhotoTag)
    .where(PhotoTag.photo == photo))

# All photos with a tag
photos = (Photo
    .select()
    .join(PhotoTag)
    .where(PhotoTag.tag == tag))
```


## Querying

Proper uses Peewee's query API directly. When a query pattern is reused across controllers or shows up more than once, extract it into a `@scope` on the model instead of repeating `.where(...)` calls. Scopes keep query logic in the model where it belongs and make controller code read like plain English. See [Scopes](models_advanced.md#scopes) for details.

Here are the most common patterns:

### Retrieving Records

```python
# Get all photos
photos = Photo.select()

# Get a single photo by primary key
photo = Photo.get_by_id(42)

# By primary key, None if not found. Prefer it in controllers: the SQL is
# generated once per model, so it costs a fraction of get_or_none
photo = Photo.find(42)

# Get a single photo by a condition, or None if not found
photo = Photo.get_or_none(Photo.published == True)

# Filter with where()
published = Photo.select().where(Photo.published == True)

# Multiple conditions (AND)
recent_published = Photo.select().where(
    Photo.published == True,
    Photo.created_at > some_date,
)

# OR conditions
Photo.select().where(
    (Photo.title == "Sunset") | (Photo.title == "Sunrise")
)

# Ordering
Photo.select().order_by(Photo.created_at.desc())

# Limit and offset
Photo.select().offset(20).limit(10)

# Count
Photo.select().where(Photo.published == True).count()
```

### Creating Records

```python
# Create and insert in one step
photo = Photo.create(title="Sunset", published=True)

# Or create an instance and save it
photo = Photo(title="Sunset")
photo.published = True
photo.save()
```

### Updating Records

```python
# Update a single instance
photo.title = "Beautiful Sunset"
photo.save()

# Update specific fields only (more efficient)
photo.title = "Beautiful Sunset"
photo.save(only=[Photo.title])

# Bulk update
Photo.update(published=False).where(Photo.views < 10).execute()
```

### Deleting Records

```python
# Delete a single instance
photo.delete_instance()

# Bulk delete
Photo.delete().where(Photo.published == False).execute()
```

### Prepared Queries

For a query that runs on most requests, compile it to SQL once with `proper.db.prepare` and mark the values with `Param`. Define it at module level, next to the model:

```python
from proper.db import Param, prepare

LAST_PAGE = prepare(
    Message.select().where(Message.room == Param("room")).order_by(Message.id.desc()).limit(Param("n"))
)

messages = list(LAST_PAGE.execute(room=room.id, n=40))
message = LAST_PAGE.first(room=room.id, n=1)  # or None
```

Values are converted by the field they are compared to (a model instance or its id for a foreign key). Results are those of the query as built (models, `.dicts()`, `.tuples()`, joins); `update()`/`delete()` work too. A `Param` can't stand for a list (`IN`), a column or a table; values that would compile to SQL, missing or unknown names, and `RETURNING` raise `ValueError`.

### Transactions

Use `db.atomic()` for transactions. Proper automatically manages database connections per request, but for operations that must be atomic you should use explicit transactions:

```python
from myapp.models import db

with db.atomic():
    photo = Photo.create(title="New Photo")
    Comment.create(body="First!", photo=photo)
    # Both are committed together, or both are rolled back on error
```

> **In controllers, import `db` the same way** — `from myapp.models import db` — and use it directly (`with db.atomic(): ...`). Don't reach through `self.app.db["main"]`; the models module re-exports `db` precisely so controllers and tasks get a short, dependency-explicit handle.


## Meta Class Options

Use the inner `Meta` class to configure table-level settings:

```python
class Event(BaseModel):
    name = pw.CharField()
    venue = pw.CharField()
    starts_at = pw.DateTimeField()
    category = pw.CharField(index=True)

    class Meta:
        table_name = "event"             # Override the auto-generated table name
        indexes = (
            # Composite indexes: (columns, unique?)
            (("starts_at", "category"), False),
            (("venue", "starts_at"), False),
        )
```


## Custom Model Methods

Add class methods and instance methods to your models as needed. This is the place to put business logic that is tightly coupled to the data:

```python
class Invitation(BaseModel):
    email = pw.CharField()
    token = pw.CharField(max_length=43, unique=True, index=True)
    accepted = pw.BooleanField(default=False)
    expires_at = pw.DateTimeField()

    @classmethod
    def create_for_email(cls, email, *, lifetime_days=7):
        return cls.create(
            email=email,
            token=secrets.token_urlsafe(32),
            expires_at=pw.utcnow() + timedelta(days=lifetime_days),
        )

    @classmethod
    def find_by_token(cls, token):
        return (
            cls.select()
            .where(
                cls.token == token,
                cls.accepted == False,
                cls.expires_at > pw.utcnow(),
            )
            .first()
        )

    def accept(self):
        self.accepted = True
        self.save(only=[Invitation.accepted])

    def is_valid(self):
        return not self.accepted and self.expires_at > pw.utcnow()
```

### Overriding save() and create()

You can override `save()` and `create()` to add custom behavior. Always call `super()` to preserve the default behavior:

```python
class Photo(BaseModel):
    title = pw.CharField()
    slug = pw.CharField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)
```

Peewee does not have a built-in event/signal system. Method overriding is the standard pattern for adding before-save or after-save behavior.


## BaseModel

Your app defines a `BaseModel` in `models/base.py`:

```python
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

- **BaseModel** - the parent class for all your models. Inherits from `ProperModel`, which adds `find()`, scope support and token generation/resolution. `Meta` is assigned instead of declared as an inner class so type checkers don't read every model's `Meta` as an override.
- **`created_at`** - every model gets it, set when the record is created. There is no `updated_at` by default: the `RussianDollCached` concern adds it ([models_advanced.md](models_advanced.md#russiandollcached)).
- **`utcnow()`** - import it from `.base` for timestamps (`from .base import BaseModel, utcnow`).


The `db` object is also exported for convenience so you can import it directly when you need the raw database instance (e.g., for `db.atomic()` transactions).


## Integration with Controllers and Forms

For the full generated controller pattern (CRUD actions, before callbacks, form handling, redirects), see [controllers.md](controllers.md#the-generated-controller).

The key model-related conventions in controllers:

- `form.save()` returns a model instance with validated data applied, **already persisted** (created or updated). No follow-up `model.save()` is needed.
- `form.save(user_id=123)` accepts extra kwargs that are set on the model before persistence.
- Forms are linked to models via `Meta.orm_cls` in the form class. See [forms.md](forms.md#orm-integration) for details.
