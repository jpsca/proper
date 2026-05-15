---
title: Models
description: Peewee ORM models — fields, relationships, querying, scopes, mixins, migrations
last_verified: 2026-04-02
---

# Models

Proper uses [Peewee ORM](https://docs.peewee-orm.com) for database access. All models inherit from `BaseModel`, which is configured to use your application's database. Peewee is used directly - there is no abstraction layer on top of it.

## Table of Contents

- [Defining Models](#defining-models)
- [Field Types](#field-types)
- [Relationships](#relationships)
- [Querying](#querying)
- [Model Concerns (Mixins)](#model-concerns-mixins)
- [Meta Class Options](#meta-class-options)
- [Custom Model Methods](#custom-model-methods)
- [Token Generation](#token-generation)
- [Database Configuration](#database-configuration)
- [Scopes](#scopes)
- [BaseModel](#basemodel)
- [Migrations](#migrations)
  - [Adding Fields to Existing Models](#adding-fields-to-existing-models)
- [Generators](#generators)
- [Integration with Controllers and Forms](#integration-with-controllers-and-forms)
- [Testing Models](#testing-models)


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

Do not import `BaseModel` or concerns/mixins here.
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

Proper includes a custom `JSONField` that extends Peewee's `TextField`. It automatically serializes Python objects to JSON when saving and deserializes them when loading, with special handling for `datetime` objects:

```python
from proper.helpers import JSONField

class Photo(BaseModel):
    title = pw.CharField()
    metadata = JSONField(null=True)
```

```python
photo = Photo.create(
    title="Sunset",
    metadata={"camera": "Canon EOS R5", "taken_at": datetime.now()},
)

# Later, when loaded from DB:
photo.metadata["camera"]     # "Canon EOS R5"
photo.metadata["taken_at"]   # datetime object (automatically deserialized)
```

The `datetime` round-trip works because the field uses a custom JSON encoder that prefixes date values with `__dt__`, preserving the type through serialization.


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
| (not set)      | Database default (usually RESTRICT)           |

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

Proper uses Peewee's query API directly. When a query pattern is reused across controllers or shows up more than once, extract it into a `@scope` on the model instead of repeating `.where(...)` calls. Scopes keep query logic in the model where it belongs and make controller code read like plain English. See [Scopes](#scopes) for details.

Here are the most common patterns:

### Retrieving Records

```python
# Get all photos
photos = Photo.select()

# Get a single photo by primary key
photo = Photo.get_by_id(42)

# Get a single photo by a condition, or None if not found
photo = Photo.get_or_none(Photo.id == 42)

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


## Model Concerns (Mixins)

Mixins let you share fields and behavior across models. They also inherit from `BaseModel`:

### Timestamped

The most commonly used mixin. It adds `created_at` and `updated_at` fields and automatically updates `updated_at` on every save:

```python
from .base import BaseModel
from .concerns.timestamped import Timestamped


class Photo(Timestamped, BaseModel):
    title = pw.CharField()
```

This adds:

- `created_at` - set to the current UTC time when the record is created
- `updated_at` - automatically set to the current UTC time on every `save()` and `update()`

The mixin works by overriding both `save()` and the classmethod `update()`:

```python
class Timestamped(BaseModel):
    created_at = pw.DateTimeField(default=pw.utcnow, null=True)
    updated_at = pw.DateTimeField(default=pw.utcnow, null=True)

    @classmethod
    def update(cls, *args, **kwargs):
        kwargs["updated_at"] = pw.utcnow()
        return super().update(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.updated_at = pw.utcnow()
        return super().save(*args, **kwargs)
```

### Writing Your Own Mixins

Create a file in `models/concerns/` and inherit from `BaseModel`:

```python
# models/concerns/publishable.py
import peewee as pw

from ..base import BaseModel


class Publishable(BaseModel):
    published = pw.BooleanField(default=False)
    published_at = pw.DateTimeField(null=True)

    def publish(self):
        self.published = True
        self.published_at = pw.utcnow()
        self.save(only=[self.__class__.published, self.__class__.published_at])

    def unpublish(self):
        self.published = False
        self.published_at = None
        self.save(only=[self.__class__.published, self.__class__.published_at])
```

Then mix it into your model:

```python
class Post(Publishable, Timestamped, BaseModel):
    title = pw.CharField()
    body = pw.TextField()
```

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
class Invitation(Timestamped, BaseModel):
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
class Photo(Timestamped, BaseModel):
    title = pw.CharField()
    slug = pw.CharField(unique=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        return super().save(*args, **kwargs)
```

Peewee does not have a built-in event/signal system. Method overriding is the standard pattern for adding before-save or after-save behavior.


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

The default `max_age` is 15 minutes.

#### Full example: email verification

```python
class User(Timestamped, BaseModel):
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



## Database Configuration

The database is configured in `config/storage.py` using the `DATABASES` dictionary. Each key is a database name, and the value specifies the driver and connection parameters:

```python
import os
import typing as t


env = os.getenv("APP_ENV", "dev")

DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

The `type` key is a dotted import path to a Peewee database class. The remaining keys are passed as keyword arguments to that class.

### SQLite (Development)

```python
DATABASES = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

### PostgreSQL (Production)

```python
DATABASES = {
    "main": {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "autoconnect": False,
    },
}
```

Set `autoconnect: False` in production. Proper manages database connections automatically per request: it opens a connection before routing and closes it after the response is sent. If an unhandled error occurs, Proper issues a rollback before closing.

### Per-Environment Overrides

The generated `config/storage.py` uses the `APP_ENV` environment variable to switch configurations:

```python
env = os.getenv("APP_ENV", "dev")

# Default (dev) database
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
}

# Override for tests
if env == "test":
    DATABASES["main"] = {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": ":memory:",
    }

# Override for production
if env == "prod":
    DATABASES["main"] = {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "autoconnect": False,
    }
```

### Multiple Databases

You can configure multiple databases for different purposes. The keys `"proper_queue"` and `"proper_cache"` are reserved for the task queue and cache backends respectively:

```python
DATABASES = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
    "analytics": {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": "analytics",
        "host": "analytics-db.internal",
    },
}
```

To use a secondary database, reference it in your model's `Meta` class:

```python
class PageView(pw.Model):
    class Meta:
        database = app.db["analytics"]
```


## Scopes

Scopes are reusable query fragments you can chain onto `select()`. They work like Rails scopes — define them once on the model, then mix and match freely.

### Defining Scopes

Import `scope` from `proper` (it's already exported in `base.py`) and decorate query methods. The first argument is the query, not `self`:

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
    def published(query):
        return query.where(Article.status == "published")

    @scope
    def popular(query, min_views=1000):
        return query.where(Article.views >= min_views)

    @scope
    def in_category(query, cat):
        return query.where(Article.category == cat)

    @scope
    def recent(query):
        return query.order_by(Article.created_at.desc())

    @scope
    def top(query, n=10):
        return query.order_by(Article.views.desc()).limit(n)
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
from proper import ProperModel, scope  # noqa

class BaseModel(ProperModel):
    class Meta:
        database = app.db["main"]
```

If a model has no `@scope` methods, it behaves exactly like a regular Peewee model with zero overhead.


## BaseModel

Your app defines a `BaseModel` in `models/base.py`:

```python
import peewee as pw
from proper import ProperModel, scope  # noqa

from ..main import app


db = app.db["main"]


class BaseModel(ProperModel):
    class Meta:
        database = app.db["main"]
```

- **BaseModel** - the parent class for all your models. Inherits from `ProperModel`, which adds scope support and token generation/resolution.


The `db` object is also exported for convenience so you can import it directly when you need the raw database instance (e.g., for `db.atomic()` transactions).


## Migrations

Proper uses [peewee-migrate](https://github.com/klen/peewee-migrate) for schema migrations. Migration files are Python scripts that live in the `db/` directory, organized by database name.

### Creating Migrations

After changing your models, create a migration that captures the changes:

```bash
proper db create "add photos table"
```

This auto-detects changes in your models (new tables, new columns, etc.) and generates a migration file in `db/main/`. The auto-detection works by comparing the current state of your models against the database schema.

You can target a specific database with the `--db` flag:

```bash
proper db create "description" --db=analytics
```

### Running Migrations

Run all pending migrations across all databases:

```bash
proper db migrate
```

Or target a specific database:

```bash
proper db migrate --db=main
```

Run migrations up to a specific target:

```bash
proper db migrate_to 003_add_comments
```

### Rolling Back

Rollback the most recent migration:

```bash
proper db rollback
```

Target a specific database:

```bash
proper db rollback --db=main
```

### Inspecting Migration Status

See which migrations have been applied:

```bash
proper db done
```

See which migrations are pending:

```bash
proper db todo
```

### Merging Migrations

If you have accumulated many small migrations during development, you can merge them into a single migration:

```bash
proper db merge "initial"
```

### Fake Migrations

Mark migrations as applied without actually running them. This is useful when you've manually applied changes to a database:

```bash
proper db migrate --fake
```

### Adding Fields to Existing Models

The most common migration workflow is adding new fields to an existing model. The steps are:

1. **Add the field to your model:**

```python
class Photo(BaseModel):
    title = pw.CharField()
    description = pw.TextField()
    status = pw.CharField(default="draft")       # new field
    featured = pw.BooleanField(default=False)     # new field
```

2. **Generate the migration:**

```bash
proper db create "add status and featured to photos"
```

This auto-detects the new fields by comparing your model definitions against the previous migration state. The generated migration will use `migrator.add_fields()`:

```python
def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.add_fields(
        'photo',
        status=pw.CharField(default='draft'),
        featured=pw.BooleanField(default=False),
    )

def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_fields('photo', 'status', 'featured')
```

3. **Apply the migration:**

```bash
proper db migrate
```

**Important:** If the table already has rows, new fields must either have a `default` value or be `null=True`. A non-nullable field without a default will fail to add to a table that contains data.

The same `proper db create` workflow also detects removed fields and changed field options (e.g., adding `unique=True` to an existing field).

### Migration File Structure

Migrations are plain Python files with `migrate()` and `rollback()` functions:

```python
"""Peewee migrations -- 002_add_photos.py."""
import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    @migrator.create_model
    class Photo(pw.Model):
        id = pw.AutoField()
        title = pw.CharField(max_length=255)
        description = pw.TextField(default="")
        published = pw.BooleanField(default=False)

        class Meta:
            table_name = "photo"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model("photo")
```

Migrations cannot be created for in-memory databases.


## Generators

### Generating a Model

The model generator creates a model file and registers it in `models/__init__.py`:

```bash
proper g model Photo title:str description:text published:bool
```

This generates `models/photo.py`:

```python
import peewee as pw

from .base import BaseModel


class Photo(BaseModel):
    title = pw.CharField()
    description = pw.TextField()
    published = pw.BooleanField()
```

#### Field Type Shortcuts

The generator supports these type names:

| Type shortcut | Peewee Field          |
|---------------|-----------------------|
| `str`         | `CharField()`         |
| `text`        | `TextField()`         |
| `int`         | `IntegerField()`      |
| `bigint`      | `BigIntegerField()`   |
| `float`       | `FloatField()`        |
| `decimal`     | `DecimalField()`      |
| `bool`        | `BooleanField()`      |
| `date`        | `DateField()`         |
| `datetime`    | `DateTimeField()`     |
| `time`        | `TimeField()`         |
| `uuid`        | `UUIDField()`         |
| `blob`        | `BlobField()`         |
| `fk`          | `ForeignKeyField()`   |

If you omit the type, it defaults to `str` (CharField).

Some aliases are also accepted: `string`/`char` for `str`, `boolean` for `bool`, `integer` for `int`, `binary` for `blob`, `numeric` for `decimal`.

#### Field Options

Add options after the type, separated by commas:

```bash
proper g model Photo title:str,unique views:int,default:0 description:text,null
```

This generates:

```python
class Photo(BaseModel):
    title = pw.CharField(unique=True)
    views = pw.IntegerField(default=0)
    description = pw.TextField(null=True)
```

Options without a value default to `True`. You can use any Peewee field option: `null`, `unique`, `index`, `default`, `primary_key`, etc.

#### Foreign Keys

Use `fk-ModelName` as the type. Add `backref` and other options with commas:

```bash
proper g model Comment body:text user:fk-User,backref:comments photo:fk-Photo,backref:comments,on_delete:CASCADE
```

This generates:

```python
class Comment(BaseModel):
    body = pw.TextField()
    user = pw.ForeignKeyField(User, backref="comments")
    photo = pw.ForeignKeyField(Photo, backref="comments", on_delete="CASCADE")
```

#### Generating with a Migration

Add `--migration` to also create a migration file:

```bash
proper g model Photo title:str description:text --migration
```

### Generating a Full Resource

The resource generator creates a model, controller, form, and views all at once:

```bash
proper g resource Photo title:str description:text published:bool
```

This generates:

- `models/photo.py` - the model
- `controllers/photo_controller.py` - a CRUD controller with all actions
- `forms/photo.py` - a form class linked to the model
- `pages/photo/` - Jinja templates for index, show, new, edit, and delete

You can limit which actions are generated:

```bash
# Only generate index and show
proper g resource Photo title:str --only=index,show

# Generate everything except delete
proper g resource Photo title:str --exclude=delete

# Singular resource (no index, no :id in URLs)
proper g resource Profile --singular

# Custom primary key placeholder
proper g resource Photo title:str --pk=uuid

# Include a migration
proper g resource Photo title:str --migration
```


## Integration with Controllers and Forms

For the full generated controller pattern (CRUD actions, before callbacks, form handling, redirects), see [controllers.md](controllers.md#the-generated-controller).

The key model-related conventions in controllers:

- `form.save()` returns a model instance with validated data applied, **already persisted** (created or updated). No follow-up `model.save()` is needed.
- `form.save(user_id=123)` accepts extra kwargs that are set on the model before persistence.
- Forms are linked to models via `Meta.orm_cls` in the form class. See [forms.md](forms.md#orm-integration) for details.


## Testing Models

The generated `tests/conftest.py` sets up a test database with automatic transaction rollback per test:

```python
import pytest

from myapp.models import db
from myapp.models.base import BaseModel


@pytest.fixture(scope="session")
def db_setup():
    # Safety check: only run on test or in-memory databases
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
def dbs(db_setup):
    with db.atomic() as transaction:
        yield
        transaction.rollback()
```

Key features:

- **Safety check** - asserts the database name contains `_test` or is `:memory:` to prevent accidentally wiping a real database
- **Auto-discovery** - finds all models via `BaseModel.__subclasses__()`
- **Transaction rollback** - every test runs inside a transaction that is rolled back after the test finishes, ensuring tests are isolated and fast
- **Fixtures** - add seed data in `load_fixtures()` that is loaded once per session

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
