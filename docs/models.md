title: Models
----

# Models

Proper uses [Peewee ORM](https://docs.peewee-orm.com) for database access. All models inherit from `BaseModel`, which is configured to use your application's database. Peewee is used directly - there is no abstraction layer on top of it.


## 1. Defining Models

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


### 1.1 Registering Models for Migrations

**Every model must be imported in `models/__init__.py`** for migration detection to work. If you forget this step, `proper db create` won't see your model changes:

```python
# models/__init__.py
"""
Import here all the models you want to be detected for migrations.
You can also do `from .your_model import *  #noqa` here
and, in your model file, use `__all__` to define what to import

Do not import `BaseModel` or `BaseMixin` here.
"""
from .base import db  # noqa
from .photo import Photo  # noqa
from .comment import Comment  # noqa
```

The model generator (`proper g model`) handles this import automatically.


## 2. Field Types

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

### 2.1 Common Field Options

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

### 2.2 JSONField

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


## 3. Relationships

### 3.1 Foreign Keys

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

### 3.2 Many-to-Many

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


## 4. Querying

Proper uses Peewee's query API directly. Here are the most common patterns:

### 4.1 Retrieving Records

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

### 4.2 Creating Records

```python
# Create and insert in one step
photo = Photo.create(title="Sunset", published=True)

# Or create an instance and save it
photo = Photo(title="Sunset")
photo.published = True
photo.save()
```

### 4.3 Updating Records

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

### 4.4 Deleting Records

```python
# Delete a single instance
photo.delete_instance()

# Bulk delete
Photo.delete().where(Photo.published == False).execute()
```

### 4.5 Transactions

Use `db.atomic()` for transactions. Proper automatically manages database connections per request, but for operations that must be atomic you should use explicit transactions:

```python
from myapp.models import db

with db.atomic():
    photo = Photo.create(title="New Photo")
    Comment.create(body="First!", photo=photo)
    # Both are committed together, or both are rolled back on error
```


## 5. Model Concerns (Mixins)

Mixins let you share fields and behavior across models. They inherit from `BaseMixin` instead of `BaseModel`:

### 5.1 Timestamped

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
class Timestamped(BaseMixin):
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

### 5.2 Writing Your Own Mixins

Create a file in `models/concerns/` and inherit from `BaseMixin`:

```python
# models/concerns/publishable.py
import peewee as pw

from ..base import BaseMixin


class Publishable(BaseMixin):
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

## 6. Meta Class Options

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


## 7. Custom Model Methods

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

### 7.1 Overriding save() and create()

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


## 8. Database Configuration

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

### 8.1 SQLite (Development)

```python
DATABASES = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

### 8.2 PostgreSQL (Production)

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

### 8.3 Per-Environment Overrides

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

### 8.4 Multiple Databases

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


## 9. BaseModel and BaseMixin

Your app defines two base classes in `models/base.py`:

```python
import peewee as pw

from ..main import app


db = app.db["main"]


class BaseModel(pw.Model):
    class Meta:
        database = app.db["main"]


class BaseMixin(pw.Model):
    class Meta:
        database = app.db["main"]
```

- **BaseModel** - the parent class for all your models. It creates a real table.
- **BaseMixin** - the parent class for mixins/concerns. It shares the same database binding but is used for multi-table inheritance (adding fields and methods to other models, not creating its own table).

The `db` object is also exported for convenience so you can import it directly when you need the raw database instance (e.g., for `db.atomic()` transactions).


## 10. Migrations

Proper uses [peewee-migrate](https://github.com/klen/peewee-migrate) for schema migrations. Migration files are Python scripts that live in the `db/` directory, organized by database name.

### 10.1 Creating Migrations

After changing your models, create a migration that captures the changes:

```bash
proper db create "add photos table"
```

This auto-detects changes in your models (new tables, new columns, etc.) and generates a migration file in `db/main/`. The auto-detection works by comparing the current state of your models against the database schema.

You can target a specific database with the `--db` flag:

```bash
proper db create "description" --db=analytics
```

### 10.2 Running Migrations

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

### 10.3 Rolling Back

Rollback the most recent migration:

```bash
proper db rollback
```

Target a specific database:

```bash
proper db rollback --db=main
```

### 10.4 Inspecting Migration Status

See which migrations have been applied:

```bash
proper db done
```

See which migrations are pending:

```bash
proper db todo
```

### 10.5 Merging Migrations

If you have accumulated many small migrations during development, you can merge them into a single migration:

```bash
proper db merge "initial"
```

### 10.6 Fake Migrations

Mark migrations as applied without actually running them. This is useful when you've manually applied changes to a database:

```bash
proper db migrate --fake
```

### 10.7 Migration File Structure

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


## 11. Generators

### 11.1 Generating a Model

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

### 11.2 Generating a Full Resource

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


## 12. Integration with Controllers and Forms

### 12.1 The Generated Controller Pattern

When you run `proper g resource Photo`, the generated controller follows this pattern:

```python
from proper.errors import NotFound
from proper.status import unprocessable

from ..forms.photo import PhotoForm
from ..models import Photo
from ..router import router
from .app_controller import AppController


@router.resource("photos")
class PhotoController(AppController):
    before = {"do": "set_photo", "exclude": ("index", "new", "create")}

    def index(self):
        self.photos = Photo.select()

    def show(self):
        pass

    def new(self):
        self.form = PhotoForm()

    def edit(self):
        self.form = PhotoForm(object=self.photo)

    def create(self):
        self.form = PhotoForm(self.params)
        if self.form.is_invalid:
            return self.render("pages/photo/new.jinja", status=unprocessable)

        photo = self.form.save()
        photo.save()
        self.response.redirect_to(
            "Photo.show",
            photo_id=photo.id,
            flash="Photo was created",
        )

    def update(self):
        self.form = PhotoForm(self.params, object=self.photo)
        if self.form.is_invalid:
            return self.render("pages/photo/edit.jinja", status=unprocessable)

        photo = self.form.save()
        photo.save()
        self.response.redirect_to(
            "Photo.show",
            photo_id=self.photo.id,
            flash="Photo was updated",
        )

    def delete(self):
        if self.photo:
            self.photo.delete_instance()
        self.response.redirect_to(
            "Photo.index",
            flash="Photo was deleted",
        )

    def set_photo(self):
        photo_id = self.params.get("photo_id", "")
        if not photo_id.isdigit():
            raise NotFound
        self.photo = Photo.get_or_none(int(photo_id))
        if self.request.matched_action != "delete" and not self.photo:
            raise NotFound
```

Key points:

- The `before` callback `set_photo` loads the model before `show`, `edit`, `update`, and `delete` actions. It is excluded from `index`, `new`, and `create` which don't need an existing record.
- Controller attributes like `self.photos` and `self.form` become template variables (`{{ photos }}`, `{{ form }}`).
- `form.save()` returns a model instance with validated data, but you still need to call `.save()` on the model to persist it to the database.
- The `delete` action checks `if self.photo` to avoid failing when deleting a record that was already deleted.

### 12.2 The Generated Form

Forms use the [formidable](https://github.com/jpsca/formidable) library and are linked to a model via `Meta.orm_cls`:

```python
import formidable as f

from ..models import Photo


class PhotoForm(f.Form):
    class Meta:
        orm_cls = Photo

    title = f.TextField()
    description = f.TextField()
    published = f.BooleanField()
```

The form handles validation. The model handles persistence. This separation keeps validation logic out of your models.


## 13. Testing Models

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
