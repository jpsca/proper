---
title: Database Migrations
description: |
  Migrations are how you change your database over time - adding tables, adding columns, renaming things - without losing the data you already have. This guide shows you how to create, apply, and roll back migrations using the `proper db` command.
number_headers: true
---

# Database Migrations

This guide covers how to evolve your database schema over time using Proper's migration system.

After reading this guide, you will know:

- What a migration is and when you need one.
- How Proper's model-driven workflow differs from frameworks where you write migrations by hand.
- How to generate, write, and apply migrations.
- The full `migrator` API for creating tables, changing fields, adding indexes, and running raw SQL.
- How to roll back, target a specific migration, and check status.
- How to manage migrations across multiple databases.
- How to squash old migrations and bring an existing database under management.

---

## Migration Overview

### What a Migration Is

A **migration** is a Python file that describes a change to your database schema - creating a table, adding a column, renaming a field, dropping an index, or any combination of these. Each migration knows how to apply the change *and* how to undo it.

Migrations exist for two reasons:

1. **Reproducibility**: every developer (and every environment) ends up with the same schema by running the same migrations in the same order.
2. **Safety**: you can change a live database without losing data, because each step is small, reviewable, and reversible.

### Your Model File IS the Schema

This is the most important thing to understand about migrations in Proper, **the model is always the source of truth, and migrations are an artifact derived from changes to it**.

```python
# models/book.py
class Book(BaseModel):
    title = pw.CharField()
    author = pw.CharField()
    published = pw.BooleanField(default=False)
```

You don't usually write a migration by hand. Instead, you edit the model and let Proper generate a migration that brings the database up to date with what the model now says.

The cycle looks like this:

1. **Edit the model** - add a field, rename one, drop one, change a default.
2. **Generate the migration** - `proper db create [name]` diffs your models against the migration history and writes a migration file.
3. **Review the file** - the generated code lives in `db/main/`. Read it, edit if needed.
4. **Apply it** - `proper db migrate`.

:::note
You can still write migrations by hand when you need to (see [Writing a Migration by Hand](#writing-a-migration-by-hand)), but day-to-day you won't.
:::

### Where Migrations Live

Migration files live in `db/<database_name>/`. For a single-database app, that means `db/main/`:

```
db/
└── main/
    ├── 001_initial.py
    ├── 002_add_book.py
    └── 003_rename_book_status.py
```

Filenames are `NNN_name.py`, where `NNN` is a three-digit zero-padded sequence number. Migrations run in numeric order.

:::warning | Sequence numbers can collide on branches
Unlike other framework's timestamp-based naming, Proper uses sequential numbers.

If two developers each create migration `005_*.py` on separate branches, you'll need to renumber one of them when merging.

For most teams this is a minor annoyance; for large teams it's worth a short merge convention (e.g. always renumber to the highest known sequence on the target branch).
:::

The history of which migrations have been applied is stored inside the database itself, in a small bookkeeping table called `migratehistory` that records which migration steps have been run.

---

## Generating a Migration

### Auto-Generating From Model Changes

The everyday command is:

```bash
proper db create [name]
```

This diffs every model imported in `models/__init__.py` against the migration history and writes a new migration file that captures the differences.

For example, if you've just added a `published` field to `Book`:

```python
class Book(BaseModel):
    title = pw.CharField()
    author = pw.CharField()
    published = pw.BooleanField(default=False)  # newly added
```

Then:

```bash
proper db create add_published_to_book
```

Will produce something like `db/main/004_add_published_to_book.py` containing the `migrate()` and `rollback()` calls needed to add (and undo) that column.

If you don't pass a name, the migration is named `auto`:

```bash
proper db create
# => db/main/004_auto.py
```

This works, but it's worth giving migrations meaningful names - they'll show up in code review, deploy logs, and your future self's `git blame`.

### Naming Migrations

Conventionally, migration names are `snake_case`, short, and describe *what* the migration does - not *why*:

| Good                            | Less good                |
| ------------------------------- | ------------------------ |
| `add_published_to_book`         | `book_changes`           |
| `rename_user_email_to_address`  | `fix_user`               |
| `drop_legacy_session_table`     | `cleanup`                |
| `create_comment`                | `comments`               |

You can use any verb that fits: `add_`, `remove_`, `rename_`, `drop_`, `create_`, `change_`, `backfill_`.

### The `proper g model` Shortcut

When you generate a brand-new model with `proper g model` - or as a part of a resource with `proper g resource` - you can also create the corresponding migration in one step by passing `--migration`:

```bash
proper g model Comment body:text book:foreign --migration
```

This generates `models/comment.py`, adds it to `models/__init__.py`, and then runs `proper db create create_comment` for you. It's the fastest way to add a new table.

Without `--migration`, only the model file is created; you'd then run `proper db create` separately.

### Writing a Migration by Hand

Sometimes you need a migration that isn't a straightforward model diff - backfilling data, running a one-off SQL fix, transforming column values, or coordinating a schema change with application code.

For these cases, generate an empty migration with a descriptive name and edit it directly:

```bash
proper db create backfill_book_slugs
```

Then open `db/main/NNN_backfill_book_slugs.py` and write the body of `migrate()` and `rollback()` yourself. See [Data Migrations: Running Python](#data-migrations-running-python) for the data-migration pattern.

---

## Anatomy of a Migration File

Every generated file follows the same shape.

### The `migrate()` and `rollback()` Functions

```python
"""Peewee migrations -- 002_add_book.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']
    > migrator.create_model(Model)
    > migrator.add_fields(model, **fields)
    > ...
"""
import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    migrator.create_model(Book)


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    migrator.remove_model(Book)
```

`migrate()` runs when the migration is applied. `rollback()` runs when it's rolled back. Both directions are *explicit* - when you generate a migration from a model diff, Proper auto-fills both, but you should always read both before merging the file.

The `fake` keyword argument lets you mark a migration as applied without actually running it. You usually trigger this from the CLI (`--fake`), not from inside the function body - see [The `--fake` Flag](#the-fake-flag).

### The `migrator` Object

The `migrator` argument is your toolkit. Every operation you'd want to do - create a table, add a column, drop an index - is a method on it:

| Method                                          | What it does                                 |
| ----------------------------------------------- | -------------------------------------------- |
| `create_model(Model)`                           | Create a table from a Peewee model class.    |
| `remove_model(Model, cascade=True)`             | Drop a table.                                |
| `add_fields(Model, **fields)`                   | Add one or more columns to a table.          |
| `change_fields(Model, **fields)`                | Change a column's type or options.           |
| `remove_fields(Model, *names, cascade=True)`    | Drop one or more columns.                    |
| `rename_field(Model, old_name, new_name)`       | Rename a column.                             |
| `rename_table(Model, new_table_name)`           | Rename a table.                              |
| `add_index(Model, *cols, unique=False)`         | Add an index over one or more columns.       |
| `drop_index(Model, *cols)`                      | Drop an index.                               |
| `add_not_null(Model, *names)`                   | Add `NOT NULL` to existing columns.          |
| `drop_not_null(Model, *names)`                  | Remove `NOT NULL` from columns.              |
| `add_default(Model, name, default)`             | Set or change a column default.              |
| `add_constraint(Model, name, sql)`              | Add a named CHECK constraint.                |
| `drop_constraints(Model, *names)`               | Drop named constraints.                      |
| `sql(query, *params)`                           | Run raw SQL.                                 |
| `run(func, *args, **kwargs)`                    | Run an arbitrary Python function.            |

You can also fetch a model by table name with `migrator.orm['<table_name>']`. This is useful inside data migrations, where you want to operate on the schema *as it was* at this migration's point in time - see [Data Migrations: Running Python](#data-migrations-running-python).

### Reading a Generated File End-to-End

Here's a real migration that adds a `Comment` table with a foreign key to `Book`:

```python
"""Peewee migrations -- 003_create_comment."""
import peewee as pw
from peewee_migrate import Migrator

def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    @migrator.create_model
    class Comment(pw.Model):
        id = pw.AutoField()
        body = pw.TextField()
        book = pw.ForeignKeyField(
            column_name="book_id",
            field="id",
            model=migrator.orm["book"],
            on_delete="CASCADE",
        )

        class Meta:
            table_name = "comment"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model(migrator.orm["comment"])
```

A few things to notice:

- The model class inside `migrate()` is **not** your application's `Comment` model. It's a snapshot of what the table should look like *at this point in history*. This is why migrations import `peewee` directly and don't import your real models - if your `Comment` model changes later, this migration must still describe the original shape.
- Foreign keys reference the related model through `migrator.orm["<table_name>"]`, not by importing the model class. Same reason.
- `@migrator.create_model` is a decorator form; `migrator.create_model(MyModel)` as a regular call works too.

---

## Writing Migrations

This section walks through every common operation. All examples assume you're inside a `migrate()` function with a `migrator` argument available.

### Creating and Removing Tables

```python
@migrator.create_model
class Tag(pw.Model):
    id = pw.AutoField()
    name = pw.CharField(unique=True)

    class Meta:
        table_name = "tag"
```

To drop a table:

```python
migrator.remove_model(migrator.orm["tag"], cascade=True)
```

`cascade=True` drops dependent objects (like foreign keys pointing at this table). Without it, the database will refuse to drop a table that other tables depend on.

### Adding, Changing, and Removing Fields

Add one or more columns to an existing table:

```python
migrator.add_fields(
    migrator.orm["book"],
    isbn=pw.CharField(null=True),
    page_count=pw.IntegerField(default=0),
)
```

Change a column's type or options:

```python
migrator.change_fields(
    migrator.orm["book"],
    title=pw.CharField(max_length=500),
)
```

Remove columns:

```python
migrator.remove_fields(migrator.orm["book"], "isbn", "page_count")
```

:::warning
`remove_fields` is destructive - once a column is dropped, the data in it is gone. Make sure you really want this before merging, and that the corresponding model attribute has already been removed (or the model would still try to read a column that no longer exists).
:::

### Renaming Tables and Fields

```python
migrator.rename_field(migrator.orm["user"], "email", "email_address")
migrator.rename_table(migrator.orm["user"], "account")
```

Renames preserve data - the column or table is renamed in place, not dropped and recreated.

### Indexes

```python
# Single-column index
migrator.add_index(migrator.orm["book"], "title")

# Composite index
migrator.add_index(migrator.orm["session"], "user_id", "revoked")

# Unique index
migrator.add_index(migrator.orm["book_tag"], "book_id", "tag_id", unique=True)

# Drop an index
migrator.drop_index(migrator.orm["book"], "title")
```

For background on when to add an index, see the Peewee ORM guide's [Indexes and Constraints](/docs/models#indexes-and-constraints) section.

### Constraints: NOT NULL, Defaults, and CHECK

Add `NOT NULL` to one or more existing columns:

```python
migrator.add_not_null(migrator.orm["book"], "isbn")
```

This will fail at the database level if any row currently has `NULL` in that column - backfill the data first (see [Data Migrations: Running Python](#data-migrations-running-python)).

Drop `NOT NULL`:

```python
migrator.drop_not_null(migrator.orm["book"], "isbn")
```

Set or change a column default:

```python
migrator.add_default(migrator.orm["book"], "views", 0)
```

Add a named CHECK constraint:

```python
migrator.add_constraint(
    migrator.orm["book"],
    "book_views_non_negative",
    "views >= 0",
)
```

Drop one:

```python
migrator.drop_constraints(migrator.orm["book"], "book_views_non_negative")
```

### Foreign Keys

Foreign keys are added like any other column, using `pw.ForeignKeyField` and referencing the parent table through `migrator.orm`:

```python
migrator.add_fields(
    migrator.orm["comment"],
    user=pw.ForeignKeyField(
        column_name="user_id",
        field="id",
        model=migrator.orm["user"],
        on_delete="SET NULL",
        null=True,
    ),
)
```

`on_delete` accepts the same values as in your model definitions: `"CASCADE"`, `"SET NULL"`, `"RESTRICT"`, `"SET DEFAULT"`, or `"NO ACTION"`. Foreign keys automatically create an index on the referencing column, so you don't need a separate `add_index` call.

### Running Raw SQL

When `migrator` doesn't have a method for what you need (database-specific features, complex updates, working with views), drop down to SQL:

```python
migrator.sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
migrator.sql(
    "UPDATE book SET status = %s WHERE status IS NULL",
    "draft",
)
```

The second argument is a tuple of bind parameters. Always use parameters - never interpolate user data into the SQL string yourself.

### Data Migrations: Running Python

Some migrations aren't about schema at all - they're about reshaping the data already in your tables. Use `migrator.run()`:

```python
def backfill_slugs(migrator):
    Book = migrator.orm["book"]
    for book in Book.select().where(Book.slug.is_null()):
        book.slug = slugify(book.title)
        book.save(only=[Book.slug])


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.add_fields(
        migrator.orm["book"],
        slug=pw.CharField(null=True),
    )
    migrator.run(backfill_slugs, migrator)
    migrator.add_not_null(migrator.orm["book"], "slug")
```

The pattern above is the canonical "add a NOT NULL column to existing rows" workflow:

1. Add the column as nullable.
2. Backfill values into every existing row.
3. Promote the column to `NOT NULL`.

:::tip | Always go through `migrator.orm`
Inside a data migration, fetch models with `migrator.orm["<table>"]` instead of importing your application model. The `orm` snapshot reflects the schema *as of this migration*. Importing your real model would couple the migration to whatever version of the model exists when the migration runs - which can break old migrations months later.
:::

---

## Running Migrations

### Applying Pending Migrations

```bash
proper db migrate
```

Runs every migration that hasn't been applied yet, in order. With no arguments, it migrates *all* registered databases. To target one:

```bash
proper db migrate --db main
```

If there's nothing to apply, it prints `No pending migrations found.` and exits.

### Migrating to a Specific Target

```bash
proper db migrate_to 003_create_comment --db main
```

Applies migrations up to and including `003_create_comment`, then stops. Useful when you're stepping forward through history during testing or debugging.

### Rolling Back

```bash
proper db rollback --db main
```

Reverses the most recently applied migration by running its `rollback()` function. Roll back one migration at a time - running this command repeatedly steps backward through history.

:::warning
Rollbacks rely on the `rollback()` function being correct. The auto-generated rollback covers most schema operations, but data migrations and raw-SQL migrations need a hand-written rollback (or an honest "this is irreversible" message). Always read the rollback before merging.
:::

### Checking Status

```bash
proper db todo --db main   # migrations not yet applied
proper db done --db main   # migrations already applied
```

Both print one filename per line.

### The `--fake` Flag

```bash
proper db migrate --fake --db main
proper db migrate_to 003_create_comment --fake --db main
```

`--fake` updates the `migratehistory` table as if the migration ran, without actually executing it. There are two cases where this is the right tool:

- **Adopting an existing database**: you're bringing a database that already has the correct schema under Proper's migration system. Run `proper db create initial` against your current models, then `proper db migrate --fake` to mark it as applied without trying (and failing) to create tables that already exist.
- **Recovering from a partial migration**: a migration ran halfway, you fixed the database state by hand, and you want to mark it as complete.

Outside those cases, don't use `--fake`. The history table will lie about what's actually in the database.

---

## Working with Multiple Databases

If your application has more than one database registered in `config/storage.py`, each one gets its own folder and its own migration history.

### One Folder Per Database

```
db/
├── main/
│   ├── 001_initial.py
│   └── 002_add_book.py
└── analytics/
    ├── 001_initial.py
    └── 002_add_page_view.py
```

Sequence numbers reset per database - `db/main/001_initial.py` and `db/analytics/001_initial.py` are independent.

### The `--db` Flag

Every `proper db` subcommand accepts `--db <name>` to target one specific database:

```bash
proper db create add_page_view --db analytics
proper db migrate --db analytics
proper db rollback --db analytics
proper db todo --db analytics
```

The default is `--db main`.

### Migrating Every Database at Once

`proper db migrate` (with no `--db` flag) applies pending migrations for *every* database in turn:

```bash
proper db migrate
# Running migrations for 'main':
# db/main/004_add_isbn.py
#
# Running migrations for 'analytics':
# db/analytics/003_add_referrer.py
```

This is what you want during deployment - a single command brings every database up to the version your code expects.

For more on registering and using multiple databases, see the Peewee ORM guide's [Using Multiple Databases](/docs/models#using-multiple-databases) section.

---

## Seed Data

A **seed** is a small Python script that puts canonical data into your database - default roles, reference data, the first admin user. Seeds differ from migrations in three important ways: they're idempotent (safe to re-run any time), they describe data your *current* schema needs, and they're not tied to a specific moment in history.

:::note | Seeds vs Migrations
Seeds are operations you want to run on every fresh database, forever. Migrations are operations tied to a single moment in your schema's history.
:::

Default roles are a seed. Backfilling existing rows after adding a column is a migration (see [Data Migrations: Running Python](#data-migrations-running-python)).

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

For applications with multiple databases, mirror the per-database layout:

```
db/
├── main/
├── analytics/
└── seeds/
    ├── main/
    │   ├── __init__.py
    │   ├── roles.py
    │   └── admin_user.py
    └── analytics/
        ├── __init__.py
        └── reference_paths.py
```

Seeds run in the order they're imported in `__init__.py`, not alphabetically. This lets you make dependencies explicit - if `admin_user` needs the `admin` role to exist first, import `roles` before `admin_user`:

```python
# db/seeds/__init__.py
from . import roles       # noqa
from . import admin_user  # noqa
```

The import list *is* the dependency graph. Reorder it to reorder the seed runs.

### Writing a Seed

Each seed file exports a `seed()` function and declares which environments it runs in:

```python
# db/seeds/roles.py
from myapp.models import Role


# APP_ENV values where this seed should run.
envs = ("dev", "test", "prod")


def seed():
    """The roles the auth system expects to exist."""
    for name in ["admin", "editor", "viewer"]:
        Role.get_or_create(name=name)
```

`seed()` takes no arguments and returns nothing. Whatever it does, it should leave the database in the same state every time you run it - which is what idempotency means in practice.

### Idempotency

A seed must be safe to run a second, third, or hundredth time without changing the database after the first run. The standard pattern is Peewee's `get_or_create`, which returns a tuple `(instance, created)` - the first run creates the row, every subsequent run finds it:

```python
Role.get_or_create(name="admin")
```

For seeds with attributes beyond the lookup key, pass `defaults`:

```python
user, created = User.get_or_create(
    email="admin@example.com",
    defaults={
        "name": "Admin",
        "password_hash": hash_password("changeme"),
    },
)
```

`defaults` are only used when *creating*. If the row already exists, the existing values are kept untouched - so re-running the seed won't reset a password that's been changed since.

For checks that don't fit `get_or_create`, fall back to an explicit existence test:

```python
if not Tag.select().where(Tag.name == "featured").exists():
    Tag.create(name="featured")
```

:::warning
Avoid plain `Model.create(...)` in seeds. The second run will hit a unique-constraint error and stop the whole seed before later inserts get a chance.
:::

### Environment-Aware Seeds

The `envs` tuple is the only knob that controls when a seed runs. `APP_ENV` is set automatically per context:

| Context           | `APP_ENV` |
| ----------------- | --------- |
| Local development | `dev`     |
| Tests             | `test`    |
| Production        | `prod`    |

Common combinations:

- `envs = ("dev", "test", "prod")` - runs in every context. Use this for data your tests rely on (e.g. default roles).
- `envs = ("dev", "prod")` - runs everywhere except tests. Use this for essential seeds whose test counterparts you'd rather control via fixtures.
- `envs = ("dev",)` - runs only on a developer's machine. Use this for sample or demo content.
- `envs = ("test",)` - runs only during tests. Rare - tests usually use fixtures.

If `APP_ENV` isn't in the tuple, the seed is skipped, and the CLI reports it as such.

There is no `--force` flag. The `envs` tuple is the absolute environment boundary - even invoking a seed by name (`proper db seed sample_books`) honors it. To run a guarded seed in another environment, change the tuple in the file.

### Running Seeds

```bash
proper db seed                  # run every seed for "main", in import order
proper db seed --db main        # same, explicit
proper db seed roles            # run a single seed by name
proper db seed --db analytics   # target a different database
```

The output reports each seed's outcome:

```
db/seeds/roles.py        - ran
db/seeds/admin_user.py   - ran
db/seeds/sample_books.py - skipped (envs=("dev",), APP_ENV=prod)
```

:::warning
`proper db migrate` does **not** run seeds. The two are deliberately separate - `migrate` is purely about schema, and seeds are always opt-in. Always run `proper db seed` explicitly.
:::

### Generating a Seed

```bash
proper g seed roles
```

Creates `db/seeds/roles.py` with a `seed()` skeleton and a default `envs = ("dev", "test", "prod")` tuple, and adds the import line to `db/seeds/__init__.py` for you. A seed file that isn't registered in `__init__.py` will never run, so always either use the generator or remember to add the import yourself.

For a multi-database app, target a specific database with `--db`:

```bash
proper g seed reference_paths --db analytics
```

### Seeds and Tests

`APP_ENV` is set to `test` during test runs, but seeds are *not* run automatically. If a test needs canonical data, call the relevant `seed()` function from a fixture:

```python
# tests/conftest.py
import pytest
from db.seeds.roles import seed as seed_roles


@pytest.fixture(autouse=True)
def setup_default_data():
    seed_roles()
```

In general, tests should use *fixtures* (model factories, explicit setup in the test file) rather than seeds. Seeds describe the canonical state of your application; tests describe the canonical state of one specific test. Mixing the two tends to leak unrelated data into tests and make failures harder to diagnose.

---

## Managing Migration History

### The `migratehistory` Table

Every database under migration control has a small bookkeeping table named `migratehistory`. It stores one row per migration that has been applied, in the order they ran. Proper reads this table to figure out which migrations are pending and which have already been done.

You shouldn't need to touch it directly - `proper db todo`, `proper db done`, and `--fake` are the tools for working with migration state. But if you ever need to inspect it (during a recovery, for instance), it's just a regular table.

### Don't Edit Applied Migrations

Once a migration has been merged and applied to any environment, treat it as immutable. Editing it after the fact won't re-run it on environments where it's already been applied - those environments will be running on the *old* version of the file forever, and your databases will silently drift.

If you need to fix something a previous migration got wrong, write a *new* migration that corrects it.

### Squashing Old Migrations

Over time, the `db/main/` folder grows. After a few hundred migrations, applying them on a fresh database becomes slow, and the history is more noise than signal. To collapse all current migrations into a single new starting point:

```bash
proper db merge initial --db main
```

This generates a single new migration (named `initial` here, but you can choose any name) that recreates the *current* state of the schema in one step, and marks the previous history as superseded. Existing environments where the old migrations have already run aren't affected - they continue to skip already-applied entries - but new environments only need to run the squashed migration.

Squash sparingly. It's an irreversible operation in the sense that the old history is rewritten; do it on a calm branch, with the team aware.

### Bringing an Existing Database Under Management

If you're adopting Proper for a database that already has tables you didn't create through migrations, the workflow is:

1. Write your models to match the existing schema.
2. Run `proper db create initial` - this generates a migration that creates all those tables.
3. Run `proper db migrate --fake` - this marks the migration as applied without actually running it (since the tables already exist).

From there, every future change goes through the normal migration flow.

---

## Common Patterns and Pitfalls

### Adding a NOT NULL Column to a Populated Table

You can't just add a `NOT NULL` column to a table that already has rows - the database has nothing to put in the new column for the existing data. The fix is a three-step migration, all in the same file:

```python
def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    # Step 1: add the column as nullable
    migrator.add_fields(
        migrator.orm["book"],
        slug=pw.CharField(null=True),
    )

    # Step 2: backfill every existing row
    def backfill(migrator):
        Book = migrator.orm["book"]
        for book in Book.select():
            book.slug = slugify(book.title)
            book.save(only=[Book.slug])

    migrator.run(backfill, migrator)

    # Step 3: enforce NOT NULL now that every row has a value
    migrator.add_not_null(migrator.orm["book"], "slug")
```

If your data set is large, consider doing the backfill in a separate, dedicated migration so it can be re-run or paused independently.

### Renaming a Column Without Downtime

A column rename is one operation in the database, but if your application code is still reading and writing the old name, requests will fail during deploy. The safe pattern is two migrations spread over two deploys:

1. **Deploy A**: add the new column, copy data into it, keep the old column. App code writes to *both* columns and reads from the new one.
2. **Deploy B**: once Deploy A is fully rolled out, drop the old column.

For small apps and short maintenance windows, a single in-place `rename_field` is fine. The two-deploy pattern is for production systems that can't afford a stale-read window.

### Writing Rollback Functions You Can Trust

The auto-generated `rollback()` is correct for any schema operation `migrator` knows about. It's not magic for the operations you write yourself:

- `migrator.sql(...)` - auto-generation has no way to invert raw SQL. Write the inverse SQL in `rollback()` yourself, or document that the migration is irreversible.
- `migrator.run(...)` - same. If you backfilled data, the rollback can't unbackfill it. Decide whether the rollback should clear the column, leave it, or raise.
- Destructive operations (`remove_fields`, `remove_model`) - the rollback can recreate the column or table, but the *data* is gone. State this in a comment, so a future reader doesn't expect a rollback to restore lost rows.

### Long-Running Migrations on Large Tables

`ALTER TABLE` on a multi-million-row table can take minutes (or hours) and lock writers during that time. A few practical tips:

- For PostgreSQL, set a `lock_timeout` and `statement_timeout` at the start of the migration, so a stuck migration fails fast instead of holding a lock indefinitely.
- For MySQL, prefer online schema-change tools (e.g. `pt-online-schema-change`, `gh-ost`) for very large tables - wrap the operation in a `migrator.sql(...)` call that invokes the tool, or run the change out-of-band and then mark the migration `--fake`.
- Split big data backfills into batches inside `migrator.run(...)`. A single `UPDATE` over ten million rows is one transaction; a hundred batches of a hundred thousand rows is a hundred small transactions, much friendlier to the database.
