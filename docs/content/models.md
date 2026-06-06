---
title: Peewee ORM
description: |
  Peewee ORM allows your models to talk to the application's database. This guide will get you started with models, the conventions Proper layers on top of Peewee, and how to create, load, update, and delete records.
number_headers: true
---

# Peewee ORM

This guide covers the fundamentals of working with database models in Proper.

After reading this guide, you will know:

- What `Peewee` is.
- How to create models that map to database tables.
- How to use models to create, read, update, and delete data.
- How to use scopes to build reusable, composable queries.
- How to share fields and behavior across models with concerns.
- How to define indexes and constraints.
- How to configure your database (SQLite, PostgreSQL, MySQL/MariaDB).

For patterns most apps don't need on day one - composite primary keys, circular FKs, polymorphic relationships, and multiple databases - see the [Advanced Models](/docs/advanced_models) guide.

---

## What is Peewee?

[Peewee](https://docs.peewee-orm.com) is what's known as an _Object Relational Mapper_ (ORM). Proper uses it to store and read data from a relational database (such as PostgreSQL, MariaDB, etc.).

An ORM lets you interact with your database using Python objects instead of writing raw SQL. Each table in your database is represented by a Python class, each row is an instance of that class, and each column is an attribute on that instance. An ORM handles the translation between the two worlds, so you can work with familiar Python objects and let the ORM generate the SQL for you.

### Knowing SQL Helps

An ORM saves you from writing SQL for the common cases, but it doesn't replace an understanding of what's happening underneath. Knowing how `SELECT`, `INSERT`, `UPDATE`, `DELETE`, joins, and indexes work will help you write efficient queries, debug slow pages, and understand the SQL that Peewee generates on your behalf.

Throughout this guide, we show the SQL that each operation produces. You don't need to memorize it, but reading it will build your intuition for what your code is actually doing.

:::note | Active Record
There are many flavors of ORMs. Peewee is one that follows the [Active Record Pattern](https://en.wikipedia.org/wiki/Active_record_pattern) (like the one from Django or Ruby on Rails).

In practice, this means a model class does double duty: it defines the shape of your data *and* provides the methods to persist it. A `Book` instance knows its own title and author, and it also knows how to `.save()` itself to the database, update its fields, or delete itself.
:::

---

## Creating Models

### BaseModel

Every model in a Proper application inherits from `BaseModel`, which is defined for you in `models/base.py` when you create a new project:

```python
# models/base.py
from proper import ProperModel, scope  # noqa

from ..main import app


db = app.db["main"]


class BaseModel(ProperModel):
    class Meta:
        database = app.db["main"]
```

`BaseModel` inherits from `ProperModel`, which is a Peewee `Model` with extra capabilities that Proper adds - namely [scopes](#scopes) and [token generation](https://docs.peewee-orm.com). If a model doesn't use any of these extras, it behaves exactly like a standard Peewee model.

To create a model, add a new file in the `models/` directory and subclass `BaseModel`:

```python
# models/book.py
import peewee as pw

from .base import BaseModel

class Book(BaseModel):
    title = pw.CharField()
    author = pw.CharField()
    published = pw.BooleanField(default=False)
    views = pw.IntegerField(default=0)
```

This creates a `Book` model mapped to a `book` table in the database, with columns `id`, `title`, `author`, `published`, and `views`. Peewee automatically adds an auto-incrementing `id` primary key unless you define one yourself.

You can also generate models from the command line:

```bash
proper g model Book title:str author:str published:bool views:int
```

:::warning | Important
Every model must be imported in `models/__init__.py` for migration auto-detection to work. The generator handles this for you, but if you create a model manually, don't forget this step:

```python
# models/__init__.py
from .base import db  # noqa
from .book import Book  # noqa
```
:::

### Fields

Fields define the columns in your table. Here are the most commonly used field types:

| Field                   | Python Type | SQL Type        |
|-------------------------|-------------|-----------------|
| `CharField()`       | `str`       | VARCHAR         |
| `TextField()`       | `str`       | TEXT            |
| `IntegerField()`    | `int`       | INTEGER         |
| `BigIntegerField()`  | `int`       | BIGINT          |
| `FloatField()`      | `float`     | REAL            |
| `DecimalField()`    | `Decimal`   | DECIMAL         |
| `BooleanField()`    | `bool`      | BOOLEAN         |
| `DateTimeField()`   | `datetime`  | DATETIME        |
| `DateField()`       | `date`      | DATE            |
| `TimeField()`       | `time`      | TIME            |
| `UUIDField()`       | `UUID`      | UUID / VARCHAR  |
| `BlobField()`       | `bytes`     | BLOB            |
| `IPField()`         | `str`       | BIGINT          |

:::tip
As you've seen in the examples, a convenient way to avoid manually importing each kind of field is to write `
import peewee as pw` and then use the `pw.` prefix.
:::

Peewee's [playhouse extensions](https://docs.peewee-orm.com/en/latest/peewee/playhouse.html) provide additional field types for specific databases, such as `ArrayField`, `HStoreField`, and `TSVectorField` for PostgreSQL. Proper also includes a `JSONField` (from `proper`) that auto-serializes Python objects to JSON with special `datetime` round-trip support.

For the full list of fields and their options, see the [Peewee field documentation](https://docs.peewee-orm.com/en/latest/peewee/models.html#field-types-table).

### Foreign Keys

Use `pw.ForeignKeyField` to define a relationship between models. The `backref` parameter creates a reverse accessor on the related model:

```python
class Comment(BaseModel):
    body = pw.TextField()
    book = pw.ForeignKeyField(Book, backref="comments", on_delete="CASCADE")
```

This creates a `book_id` column in the `comment` table. You can now traverse the relationship in both directions:

```python
# From a comment, access its book
comment.book           # => Book instance

# From a book, access all its comments
book.comments          # => SelectQuery (iterable, filterable)
```

The `on_delete` parameter controls what happens when the referenced record is deleted.

You can learn more about relationships in the [Relationships and Joins guide](/docs/relationships).

### Default Values

Every field accepts a `default` parameter. It can be a static value or a callable:

```python
class Book(BaseModel):
    title = pw.CharField()
    status = pw.CharField(default="draft")           # Static default
    views = pw.IntegerField(default=0)               # Static default
    created_at = pw.DateTimeField(default=pw.utcnow) # Callable default (called at insert time)
```

When a callable is used (note: no parentheses - `pw.utcnow`, not `pw.utcnow()`), Peewee calls it each time a new record is created, so every record gets its own timestamp.

Fields are non-nullable by default. If a column should allow `NULL`, pass `null=True`:

```python
description = pw.TextField(null=True)
```

---

## Overriding Naming Conventions

:::tip
Avoid breaking conventions if you can. Your code should strive to be as _boringly predictable_ as possible, so that a human (yourself included) or an AI agent doesn't waste time or tokens figuring out how things work.
:::

### Table Names

By default, Peewee uses the lowercased class name as the table name. `Book` maps to `book`, `PhotoTag` maps to `phototag`. Unlike some other ORMs, Peewee does **not** pluralize table names automatically.

You can override the table name in the `Meta` class:

```python
class Book(BaseModel):
    title = pw.CharField()
    author = pw.CharField()

    class Meta:
        table_name = "books"
```

This is useful when working with a legacy database.

### Primary Keys

Peewee adds an auto-incrementing integer `id` column as the primary key by default. You can override this:

```python
import uuid

class Book(BaseModel):
    # Use a UUID primary key instead of auto-increment
    id = pw.UUIDField(primary_key=True, default=uuid.uuid4)
    title = pw.CharField()
```

Or use a custom column name:

```python
class LegacyBook(BaseModel):
    book_id = pw.AutoField()  # This becomes the primary key
    title = pw.CharField()

    class Meta:
        table_name = "legacy_books"
```

If you set `primary_key = False` in `Meta`, Peewee won't create an `id` column at all. This is occasionally useful for join tables or views, but in general you should always have a primary key.

---

## CRUD: Reading and Writing Data

CRUD stands for **C**reate, **R**ead, **U**pdate, and **D**elete - the four basic operations for persistent data. Peewee provides Python methods for each one, so you can work with your data as objects rather than writing SQL by hand.

The examples below use a `Book` model:

```python
class Book(BaseModel):
    title = pw.CharField()
    author = pw.CharField()
    published = pw.BooleanField(default=False)
    views = pw.IntegerField(default=0)
```

:::note | Cheatsheet
```python
# INSERT into the database
book = Book.create(title="The Hobbit", author="J.R.R. Tolkien")
# UPDATE the existing row
book.title = "The Hobbit: There and Back Again"
book.save()       
# DELETE the row
book.delete_instance()
```
:::

### Create

There are two ways to create a new record. The `create()` class method builds the object and inserts it in one step:

```python
book = Book.create(title="The Hobbit", author="J.R.R. Tolkien")

book.id       # => 1 (assigned by the database)
book.title    # => "The Hobbit"
```

The resulting SQL:

```sql
INSERT INTO "book" ("title", "author", "published", "views")
VALUES ('The Hobbit', 'J.R.R. Tolkien', false, 0)
```

Alternatively, you can instantiate the object, set its attributes, and call `save()`:

```python
book = Book()
book.title = "The Lord of the Rings"
book.author = "J.R.R. Tolkien"
book.save()
```

The SQL is the same. Using `save()` on a new object (one without a primary key value) performs an `INSERT`.

To insert many records at once, use `insert_many()`:

```python
data = [
    {"title": "Dune", "author": "Frank Herbert"},
    {"title": "Neuromancer", "author": "William Gibson"},
]
Book.insert_many(data).execute()
```

### Read

Peewee provides a rich query API for reading data. All queries start with `Model.select()`.

```python
# Return all books
books = Book.select()

# Get a single book by primary key
book = Book.get_by_id(1)

# Get a single book by condition, or None if not found
book = Book.get_or_none(Book.title == "The Hobbit")
```

The resulting SQL for each:

```sql
-- Book.select()
SELECT "t1"."id", "t1"."title", "t1"."author", "t1"."published", "t1"."views"
FROM "book" AS "t1"

-- Book.get_by_id(1)
SELECT "t1"."id", "t1"."title", "t1"."author", "t1"."published", "t1"."views"
FROM "book" AS "t1"
WHERE ("t1"."id" = 1) LIMIT 1

-- Book.get_or_none(Book.title == "The Hobbit")
SELECT "t1"."id", "t1"."title", "t1"."author", "t1"."published", "t1"."views"
FROM "book" AS "t1"
WHERE ("t1"."title" = 'The Hobbit') LIMIT 1
```

You can filter, order, paginate, and count:

```python
# Filter with where()
published_books = Book.select().where(Book.published == True)

# Multiple conditions (AND)
popular_tolkien = Book.select().where(
    Book.author == "J.R.R. Tolkien",
    Book.views >= 1000,
)

# OR conditions
Book.select().where(
    (Book.author == "Frank Herbert") | (Book.author == "Ursula K. Le Guin")
)

# Ordering
Book.select().order_by(Book.views.desc())

# Pagination
Book.select().paginate(2, 20)  # Page 2, 20 per page

# Count
Book.select().where(Book.published == True).count()
```

The resulting SQL for the filter example:

```sql
-- published_books
SELECT "t1"."id", "t1"."title", "t1"."author", "t1"."published", "t1"."views"
FROM "book" AS "t1"
WHERE ("t1"."published" = true)

-- popular_tolkien
SELECT "t1"."id", "t1"."title", "t1"."author", "t1"."published", "t1"."views"
FROM "book" AS "t1"
WHERE (("t1"."author" = 'J.R.R. Tolkien') AND ("t1"."views" >= 1000))
```

For the full query API, see the [Peewee query documentation](https://docs.peewee-orm.com/en/latest/peewee/querying.html).

### Update

Once you've retrieved a record, modify its attributes and call `save()`:

```python
book = Book.get_by_id(1)
book.title = "The Hobbit: There and Back Again"
book.save()
```

The resulting SQL:

```sql
UPDATE "book"
SET "title" = 'The Hobbit: There and Back Again',
    "author" = 'J.R.R. Tolkien',
    "published" = false,
    "views" = 0
WHERE ("book"."id" = 1)
```

By default, `save()` writes all fields. If you only want to update specific columns (more efficient for wide tables), pass `only`:

```python
book.title = "The Hobbit: There and Back Again"
book.save(only=[Book.title])
```

```sql
UPDATE "book"
SET "title" = 'The Hobbit: There and Back Again'
WHERE ("book"."id" = 1)
```

For bulk updates that don't need to load records into Python, use `update()`:

```python
Book.update(published=True).where(Book.views >= 1000).execute()
```

```sql
UPDATE "book" SET "published" = true WHERE ("book"."views" >= 1000)
```

### Delete

To delete a single record, call `delete_instance()` on it:

```python
book = Book.get_by_id(1)
book.delete_instance()
```

```sql
DELETE FROM "book" WHERE ("book"."id" = 1)
```

For bulk deletion:

```python
Book.delete().where(Book.published == False).execute()
```

```sql
DELETE FROM "book" WHERE ("book"."published" = false)
```

### Transactions

Sometimes a set of changes must be applied as a whole. For example, moving money between two accounts, but only if there is enough in the source account.

For that kind of thing, use `db.atomic()` to wrap multiple operations in a single "transaction". If any operation fails, all changes are rolled back:

```python
from myapp.models import db

with db.atomic():
    book = Book.create(title="New Book", author="New Author")
    Comment.create(body="Great read!", book=book)
    # Both are committed together, or both rolled back on error
```

Proper automatically manages database connections per request - it opens a connection before routing and closes it after the response is sent.

---

## Scopes

### What Are Scopes?

Scopes are reusable query fragments that you define once on a model and chain freely onto any query. They keep your query logic in the model - where it belongs - instead of scattering `.where(...)` calls across controllers and templates.

Without scopes, you end up repeating the same filters everywhere:

```python
# In one controller
published_articles = Article.select().where(Article.status == "published")

# In another controller
popular_published = (
    Article.select()
    .where(Article.status == "published")
    .where(Article.views >= 1000)
)

# In a template helper
recent_published = (
    Article.select()
    .where(Article.status == "published")
    .order_by(Article.created_at.desc())
)
```

With scopes, the query logic lives on the model and reads like plain English:

```python
Article.select().published()
Article.select().published().popular()
Article.select().published().recent()
```

### Defining Scopes

Import `scope` from `proper` (it's already available in `base.py`) and decorate methods on your model. The first argument is the query - not `self`:

```python
# models/article.py
import peewee as pw

from .base import BaseModel, scope


class Article(BaseModel):
    title = pw.CharField()
    status = pw.CharField(default="draft")
    views = pw.IntegerField(default=0)
    category = pw.CharField(default="general")
    created_at = pw.DateTimeField(default=pw.utcnow)

    @scope
    def published(query):
        return query.where(Article.status == "published")

    @scope
    def draft(query):
        return query.where(Article.status == "draft")

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

Scopes can accept arguments (like `popular(min_views=1000)`) or use sensible defaults.

### Using Scopes

Chain scopes after `.select()`. They compose freely with each other and with standard Peewee methods:

```python
# Chain multiple scopes
articles = Article.select().published().popular(500).in_category("tech")

# Mix scopes with native Peewee methods
articles = (
    Article.select()
    .published()
    .where(Article.title.contains("Python"))
    .paginate(1, 20)
)

# Reuse a base query
base = Article.select().published().recent()
tech_articles    = base.in_category("tech").top(5)
science_articles = base.in_category("science").top(5)
```

Scopes are preserved through `where()`, `order_by()`, `join()`, `switch()`, `paginate()`, `limit()`, `offset()`, and all other query-building methods. Terminal methods like `count()`, `exists()`, or iterating the query execute normally:

```python
# count() works after scopes
Article.select().published().popular().count()

# Scopes work across joins
Comment.select().approved_only().join(Article).where(Article.category == "tech")
```

Each model's scopes are independent - `Article.select()` has `.published()` and `.popular()`, but `User.select()` does not. If a model has no `@scope` methods, it behaves exactly like a standard Peewee model with zero overhead.

---

## Model Concerns (Mixins)

When multiple models share the same fields or behavior, you can extract that shared code into a **concern** (also called a mixin). A concern is a regular `BaseModel` subclass that you reuse as a parent for other models.

::: warning | Important
You might wonder why a `BaseModel` subclass doesn't get its own database table. The answer is simple: Proper only creates tables for models imported in `models/__init__.py`, and concerns are deliberately *not* imported there. They exist purely to be inherited from.
:::

### Using a Concern

Concerns live in the `models/concerns/` directory. To use one, add it to your model's inheritance chain **before** `BaseModel`:

```python
# models/post.py
import peewee as pw

from .base import BaseModel
from .concerns.timestamped import Timestamped
from .concerns.publishable import Publishable


class Post(Publishable, Timestamped, BaseModel):
    title = pw.CharField()
    body = pw.TextField()
```

The `Post` table now has all the columns defined in `Publishable` and `Timestamped`, plus its own `title` and `body`.

### Writing a Concern

Create a file in `models/concerns/` and define a normal `BaseModel` subclass:

```python
# models/concerns/timestamped.py
import peewee as pw

from ..base import BaseModel


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

Here's another example - a `Publishable` concern that adds publish/unpublish behavior:

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

The key points:

- Inherit from `BaseModel`, just like any other model.
- **Don't** import the concern in `models/__init__.py` - that's what keeps it from getting its own table.
- Define fields, instance methods, and class methods just like a normal model.
- Always call `super()` when overriding `save()`, `create()`, or `update()` so other concerns in the chain get a chance to run.

---

## Indexes and Constraints

Indexes make queries faster. Constraints enforce data integrity. Peewee lets you define both at the field level and at the table level.

### Field-Level Options

Every field accepts options that translate to column constraints:

```python
class User(BaseModel):
    email = pw.CharField(unique=True)     # UNIQUE constraint
    username = pw.CharField(index=True)   # Single-column index
    bio = pw.TextField(null=True)         # Allow NULL
    role = pw.CharField(default="member") # Default value
```

The resulting SQL (for the table creation):

```sql
CREATE TABLE "user" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "username" VARCHAR(255) NOT NULL,
    "bio" TEXT,
    "role" VARCHAR(255) NOT NULL DEFAULT 'member'
)

CREATE INDEX "user_username" ON "user" ("username")
```

### Composite Indexes

For indexes that span multiple columns, use the `indexes` tuple in the `Meta` class:

```python
class Session(BaseModel):
    token = pw.CharField(max_length=43, unique=True, index=True)
    user = pw.ForeignKeyField(User, backref="sessions", on_delete="CASCADE")
    created_at = pw.DateTimeField(default=pw.utcnow)
    expires_at = pw.DateTimeField()
    revoked = pw.BooleanField(default=False)

    class Meta:
        indexes = (
            # (column_tuple, is_unique)
            (("expires_at", "revoked"), False),  # For cleanup queries
            (("user", "revoked"), False),         # For "my active sessions"
        )
```

Each entry in `indexes` is a tuple of `(columns, unique)`:

- `columns` - a tuple of column names as strings.
- `unique` - `True` to create a unique index, `False` for a regular one.

### Unique Together

A composite unique index ensures that the *combination* of values is unique, even if individual values can repeat:

```python
class BookTag(BaseModel):
    book = pw.ForeignKeyField(Book, on_delete="CASCADE")
    tag = pw.ForeignKeyField(Tag, on_delete="CASCADE")

    class Meta:
        indexes = (
            (("book", "tag"), True),  # A book can have each tag only once
        )
```

### Foreign Key Constraints

As covered in [Foreign Keys](#foreign-keys), foreign keys automatically create an index on the referencing column. Use `on_delete` to control cascading behavior:

```python
class Comment(BaseModel):
    book = pw.ForeignKeyField(Book, backref="comments", on_delete="CASCADE")
    user = pw.ForeignKeyField(User, backref="comments", on_delete="SET NULL", null=True)
```

When a `Book` is deleted, its comments are deleted too (`CASCADE`). When a `User` is deleted, their comments remain but the `user` column is set to `NULL` (`SET NULL`).

---

## Configuring Your Database

Your application's database is configured in `config/storage.py`, under the `DATABASES` dict. New projects start with SQLite so you can run the app without installing anything else, but you can swap in PostgreSQL, MySQL, or MariaDB by changing a few keys.

Each entry in `DATABASES` is a dictionary with two required keys:

- `type`: the import path of a Peewee `Database` class.
- `database`: the database name (or file path, for SQLite).

Any other keys are passed straight through to the database class as keyword arguments.

### SQLite

This is the default. It needs no extra dependencies - SQLite ships with Python:

```python
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

For tests, the blueprint already overrides this to `":memory:"`, so each test run starts with a clean in-memory database.

`SqliteExtDatabase` (from `playhouse`) is preferred over the plain `peewee.SqliteDatabase` because it enables useful extensions like JSON support and full-text search.

### PostgreSQL

```python
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    },
}
```

You'll need to install a PostgreSQL driver:

```bash
uv add 'psycopg[binary,pool]'
```

`PostgresqlExtDatabase` adds support for PostgreSQL-specific field types like `ArrayField`, `HStoreField`, `JSONField`, and `TSVectorField` (full-text search).

### MySQL and MariaDB

```python
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "peewee.MySQLDatabase",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "charset": "utf8mb4",
    },
}
```

Install a driver:

```bash
uv add pymysql
```

`pymysql` is pure-Python and works with both MySQL and MariaDB. If you'd rather use the official MariaDB connector (faster, but requires the `mariadb` C library installed on your system), set `type` to `playhouse.mysql_ext.MariaDBConnectorDatabase` and run `uv add mariadb`.

:::tip | Connection pooling
For production workloads with many concurrent requests, swap the database class for one of the pooled variants in `playhouse.pool` (e.g. `playhouse.pool.PooledPostgresqlExtDatabase`). Pooled classes accept the same keys plus `max_connections` and `stale_timeout`.
:::
