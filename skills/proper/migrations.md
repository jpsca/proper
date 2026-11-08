---
title: Databases, Migrations and Seeds
description: DATABASES config (SQLite, PostgreSQL, several databases), migrations (create, migrate, rollback, merge, fake, adding fields), and seeds (`db/seeds/`, `envs`, `proper db seed`)
last_verified: 2026-11-07
sources:
  - src/proper/models
  - src/proper/db
  - src/proper/cli/db_cli.py
  - blueprint/[[app_name]]/config/storage.tt.py
---

# Databases, Migrations and Seeds

How the schema gets to the database. Models are in [models.md](models.md).

## Table of Contents

- [Database Configuration](#database-configuration)
- [Migrations](#migrations)
- [Seeds](#seeds)


## Database Configuration

The database is configured in `config/storage.py` using the `DATABASES` dictionary. Each key is a database name, and the value specifies the driver and connection parameters:

```python
import os
import typing as t


env = os.getenv("APP_ENV", "dev")

DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "peewee.SqliteDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

Each entry needs `type` (a dotted import path to a Peewee database class, or the class itself) and `database`; the remaining keys are passed as keyword arguments to that class. `None` instead of a dict disables that database.

### SQLite (Development)

```python
DATABASES = {
    "main": {
        "type": "peewee.SqliteDatabase",
        "database": "storage/app.sqlite3",
    },
}
```

### PostgreSQL (Production)

```python
DATABASES = {
    "main": {
        "type": "playhouse.postgres_ext.PooledPsycopg3Database",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    },
}
```

`PooledPsycopg3Database` is what the blueprint writes in its `prod` branch; psycopg needs the `libpq5` system library (the blueprint's Docker image installs it). For a database configured with `"autoconnect": False`, Proper manages the connection per request: it opens one before routing and closes it after the response is sent, with a rollback first if an unhandled error occurs. A database with Peewee's default `autoconnect=True` connects by itself on the first query.

### Per-Environment Overrides

The generated `config/storage.py` uses the `APP_ENV` environment variable to switch configurations:

```python
env = os.getenv("APP_ENV", "dev")

# Default (dev) database
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "peewee.SqliteDatabase",
        "database": "storage/app.sqlite3",
    },
}

# Override for tests
if env == "test":
    DATABASES["main"] = {
        "type": "peewee.SqliteDatabase",
        "database": ":memory:",
    }

# Override for production
if env == "prod":
    DATABASES["main"] = {
        "type": "playhouse.postgres_ext.PooledPsycopg3Database",
        "database": os.getenv("DB_NAME", "myapp"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
```

### Multiple Databases

You can configure multiple databases for different purposes. The keys `"proper_queue"` and `"proper_cache"` are reserved for the task queue and cache backends respectively:

```python
DATABASES = {
    "main": {
        "type": "peewee.SqliteDatabase",
        "database": "storage/app.sqlite3",
    },
    "analytics": {
        "type": "playhouse.postgres_ext.PooledPsycopg3Database",
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


## Migrations

Proper has its own schema migrations for Peewee, in `proper.models.migrate`. Migration files are Python scripts that live in the `db/` directory, organized by database name.

### Creating Migrations

After changing your models, create a migration that captures the changes:

```bash
proper db create "add photos table"
```

This auto-detects changes in your models (new tables, new columns, etc.) and generates a migration file in `db/main/`. The auto-detection works by comparing the current state of your models against the migrations already written.

You can target a specific database with the `--db` flag:

```bash
proper db create "description" --db=analytics
```

It writes only the models stored in that database (`Meta.database` is `app.db["analytics"]`).

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

`proper db prepare` runs `proper db migrate` and then `proper db seed` (the seeds are skipped when `APP_ENV=test`); `--db NAME` limits both to one database. `proper db migrate` without `--db` covers every database, `proper_queue` and `proper_cache` included; every other `proper db` command acts on `main` unless you pass `--db NAME`.

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

`proper run` warns before serving when a database has migrations that were not applied (`proper.models.migrations.pending_migrations(app)`, `{db: [migration, ...]}`; it only reads). `app.has_migrations_pending()` is the same check as a bool.

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
        "photo",
        status=pw.CharField(default="draft", max_length=255),
        featured=pw.BooleanField(default=False),
    )

def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_fields('photo', 'status', 'featured')
```

3. **Apply the migration:**

```bash
proper db migrate
```

**Important:** New fields must either have a `default` value or be `null=True`. `add_fields` refuses a non-nullable field without a default with a `ValueError`, rows or not, unless it is called with `allow_not_null=True` (then the database decides: SQLite and PostgreSQL refuse it on a table with rows).

The same `proper db create` workflow also detects removed fields and changed field options (e.g., adding `unique=True` to an existing field).

### Migration File Structure

Migrations are plain Python files with `migrate()` and `rollback()` functions:

```python
"""Peewee migrations -- 002_add_photos.py."""
import peewee as pw
from proper.models.migrate import Migrator


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

No migration command of `proper db` runs against an in-memory database (`"database": ":memory:"`); the test configuration relies on this. The generated file's docstring also lists every `migrator` method (`add_fields`, `change_fields`, `rename_field`, `add_index`, ...), and the file is formatted with `ruff` when it is on the `PATH`.


## Seeds

A **seed** is a small, idempotent script that inserts canonical data into the database — default roles, reference rows, the first admin user. Seeds describe data the *current* schema needs; migrations describe schema changes pinned to a single moment in history. Run `proper db migrate` to set up the schema, then `proper db seed` to populate it.

### Where Seeds Live

Seeds live in `db/seeds/`, parallel to the per-database migration folders:

```
db/
├── main/                       # migrations for "main"
│   ├── 001_initial.py
│   └── 002_add_book.py
└── seeds/
    ├── __init__.py
    ├── roles.py
    └── admin_user.py
```

For multi-database apps, mirror the per-database layout (`db/seeds/<db_name>/`).

The import order in `db/seeds/__init__.py` *is* the dependency graph:

```python
# db/seeds/__init__.py
from . import roles       # noqa
from . import admin_user  # noqa
```

A seed file that isn't imported here will never run.

### Writing a Seed

Each seed file exports a `seed()` function and declares which `APP_ENV` values it runs in:

```python
# db/seeds/roles.py
from myapp.models import Role


envs = ("dev", "test", "prod")


def seed():
    for name in ["admin", "editor", "viewer"]:
        Role.get_or_create(name=name)
```

`seed()` takes no arguments and returns nothing. It must be safe to run repeatedly — use `get_or_create` (or an explicit existence check) and avoid plain `Model.create(...)`, which will hit a unique-constraint error on the second run.

For seeds with attributes beyond the lookup key, pass `defaults`:

```python
user, _ = User.get_or_create(
    email="admin@example.com",
    defaults={"name": "Admin", "password_hash": hash_password("changeme")},
)
```

`defaults` are only used when *creating*, so re-running the seed never overwrites values that changed in the interim.

### Environment-Aware Seeds

`APP_ENV` is set automatically: `dev` locally, `test` during tests, `prod` in production. The `envs` tuple is the only knob — there is intentionally no `--force` flag.

- `("dev", "test", "prod")` — every context.
- `("dev", "prod")` — everywhere except tests.
- `("dev",)` — only on a developer's machine (sample/demo content).

If `APP_ENV` isn't in the tuple, the seed is skipped and the CLI reports it as such.

### Running Seeds

```bash
proper db seed                  # run every seed for "main", in import order
proper db seed roles            # run a single seed by name
proper db seed --db analytics   # target a different database
```

`proper db migrate` does **not** run seeds — schema and seed data are deliberately separate.

### Generating a Seed

```bash
proper g seed roles
proper g seed reference_paths --db analytics
```

The generator creates `db/seeds/<name>.py` with a `seed()` skeleton and `envs = ("dev", "test", "prod")`, and adds the import line to `db/seeds/__init__.py`.

### Seeds and Tests

Seeds are not run automatically during tests. If a test needs canonical data, call the seed function from a fixture:

```python
# tests/conftest.py
from db.seeds.roles import seed as seed_roles

@pytest.fixture(autouse=True)
def setup_default_data():
    seed_roles()
```

In general, tests should use fixtures (model factories, explicit setup) rather than seeds — seeds describe the canonical state of the application, not the state of one specific test.
