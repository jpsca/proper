---
title: Models Advanced Topics
description: |
  Most applications never need these features, but when you do, you really do. This guide covers four model patterns that break the default mold: composite primary keys, circular foreign keys, polymorphic relationships, and using more than one database.
number_headers: true
---

# Models Advanced Topics

This guide collects the model patterns you don't reach for every day, but that you'll be glad to find documented when you do. Each section is independent - read whichever applies to your problem.

After reading this guide, you will know:

- When (and when not) to give a model a composite primary key.
- How to declare two models that reference each other with `DeferredForeignKey`.
- Three patterns for modeling a child that can have one of several parent types.
- How to register a second database, point a model at it, and live with the constraints that come from data living in two places.

---

## Composite Primary Keys

By default, every Peewee model has an auto-incrementing integer `id` as its primary key. For most tables that's the right choice. But for some - typically join tables - the *combination* of two foreign keys is naturally unique, and an extra `id` column adds nothing.

Set `primary_key` in `Meta` to a `CompositeKey`:

```python
class ArticleTag(BaseModel):
    article = pw.ForeignKeyField(Article, on_delete="CASCADE")
    tag = pw.ForeignKeyField(Tag, on_delete="CASCADE")
    added_at = pw.DateTimeField(default=pw.utcnow)

    class Meta:
        primary_key = pw.CompositeKey("article", "tag")
```

Now `(article_id, tag_id)` is the primary key. There's no `id` column, and the unique-together constraint comes for free.

:::note | Trade-offs
Composite keys are honest about the data model - but they're slightly less convenient:

- You can't look up rows with `get_by_id(...)`; use `.get(article=a, tag=t)`.
- Other models can't `ForeignKeyField` to a composite-key model without extra work.
- Some ORM-adjacent tools (admin scaffolds, JSON serializers, etc.) assume a single-column id.

For pure join tables, the trade-off is usually worth it. For anything else, prefer a surrogate `id` plus a unique-together index.
:::

---

## Circular Foreign Keys

Occasionally two models need to reference each other. A `User` has a `default_team`, and a `Team` has an `owner` who is a `User`. Neither class can reference the other directly because Python evaluates them top-to-bottom: whichever you write second, the first one can't see it yet.

The fix is `pw.DeferredForeignKey`, which holds the reference open until both classes are loaded:

```python
import peewee as pw

from .base import BaseModel


class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)
    default_team = pw.DeferredForeignKey("Team", null=True,
                                         backref="default_for_users")


class Team(BaseModel):
    name = pw.CharField()
    owner = pw.ForeignKeyField(User, backref="owned_teams",
                               on_delete="RESTRICT")
```

`DeferredForeignKey` resolves the string `"Team"` once the class exists, then behaves like a regular `ForeignKeyField`.

:::warning | Often a code smell
Circular references are usually a sign that one of two things is wrong:

1. The relationship belongs on a *third* model. Maybe `Membership(user, team, role)` is the real concept, and "owner" is a role on a membership.
2. One of the two columns is denormalized. A team's owner could be looked up via the membership table; a user's default team could be a session preference, not a column.

Try to redesign before reaching for `DeferredForeignKey`. Sometimes you really do need it - but check first.
:::

---

## Polymorphic Relationships

A polymorphic relationship is when one model can belong to *one of several* parent models. The classic example is `Reaction` or `Comment` - you might want to attach them to articles, photos, or events.

Peewee has no native support for polymorphic foreign keys. You write the pattern yourself, and the right pattern depends on how disciplined you want the database to be.

### Pattern A: Discriminator + Nullable FKs

Best for two or three known parent types. You add a `parent_type` column and one nullable FK per possible parent:

```python
class Reaction(BaseModel):
    user = pw.ForeignKeyField(User, backref="reactions", on_delete="CASCADE")
    parent_type = pw.CharField()      # "article" or "comment"
    article = pw.ForeignKeyField(Article, null=True,
                                 backref="reactions", on_delete="CASCADE")
    comment = pw.ForeignKeyField(Comment, null=True,
                                 backref="reactions", on_delete="CASCADE")
    kind = pw.CharField()             # "like", "heart", etc.

    class Meta:
        constraints = [
            pw.Check(
                "(parent_type = 'article' AND article_id IS NOT NULL "
                " AND comment_id IS NULL) "
                "OR (parent_type = 'comment' AND comment_id IS NOT NULL "
                " AND article_id IS NULL)"
            )
        ]
```

The check constraint enforces "exactly one of the FK columns is set, matching the discriminator". You keep real FK constraints (so cascades work), real indexes (so queries are fast), and clear semantics - at the cost of a column per parent type.

Resolving the parent looks like this:

```python
class Reaction(BaseModel):
    # ... fields above ...

    @property
    def parent(self):
        if self.parent_type == "article":
            return self.article
        return self.comment
```

### Pattern B: Shared Parent Table

When the parent types share a lot of behavior, give them a real parent table:

```python
class Postable(BaseModel):
    # Shared identity, common fields, shared lifecycle
    created_at = pw.DateTimeField(default=pw.utcnow)


class Article(BaseModel):
    postable = pw.ForeignKeyField(Postable, unique=True, on_delete="CASCADE")
    title = pw.CharField()
    body = pw.TextField()


class Photo(BaseModel):
    postable = pw.ForeignKeyField(Postable, unique=True, on_delete="CASCADE")
    caption = pw.CharField()
    image_url = pw.CharField()


class Reaction(BaseModel):
    postable = pw.ForeignKeyField(Postable, backref="reactions",
                                  on_delete="CASCADE")
    user = pw.ForeignKeyField(User, on_delete="CASCADE")
    kind = pw.CharField()
```

`Reaction.postable` is a single, real foreign key. The cost is that every "post-like" thing has two rows (one in `postable`, one in its specific table) and you join through `Postable` to navigate.

This is heavier than Pattern A but scales much better when you have many parent types or when the shared behavior is meaningful (timestamps, audit trail, soft-deletes).

### Pattern C: `GFKField` from `playhouse.gfk`

Peewee's playhouse offers a generic foreign key - a `(parent_type, parent_id)` pair where `parent_id` is just an integer with no FK constraint:

```python
from playhouse.gfk import GFKField, ReverseGFK


class Reaction(BaseModel):
    parent_type = pw.CharField()
    parent_id   = pw.IntegerField()
    parent      = GFKField("parent_type", "parent_id")


class Article(BaseModel):
    reactions = ReverseGFK(Reaction, "parent_type", "parent_id")
```

Convenient - but you give up the integrity guarantees that make foreign keys worth declaring in the first place. There's no cascade, no FK constraint, and no protection against orphan rows. Use this only when the parent set is genuinely open-ended (plugins, user-defined types).

### Which to Pick

| Situation                                          | Pattern   |
|----------------------------------------------------|-----------|
| Two or three parent types, set in stone            | A         |
| Parents share meaningful behavior                  | B         |
| Many parent types, or extensible at runtime        | C         |

When in doubt, start with A. It's the easiest to migrate away from later.

---

## Multiple Databases

Most applications only need one database, and the default `BaseModel` setup in `models/base.py` is all you'll ever touch. But sometimes you need more than one - a read replica for heavy analytics queries, a separate reporting database, integration with a legacy system you can't migrate away from, or per-tenant isolation.

Proper supports any number of databases out of the box. Each one is registered by name in `config/storage.py` and exposed as `app.db["<name>"]`.

### Registering an Extra Database

Open `config/storage.py` and add another entry to the `DATABASES` dict:

```python
# config/storage.py
DATABASES: dict[str, t.Any] = {
    "main": {
        "type": "playhouse.sqlite_ext.SqliteExtDatabase",
        "database": "storage/app.sqlite3",
    },
    "analytics": {
        "type": "playhouse.postgres_ext.PostgresqlExtDatabase",
        "database": os.getenv("ANALYTICS_DB_NAME", "analytics"),
        "host": os.getenv("ANALYTICS_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("ANALYTICS_DB_PORT", 5432)),
        "user": os.getenv("ANALYTICS_DB_USER", "root"),
        "password": os.getenv("ANALYTICS_DB_PASSWORD", ""),
    },
}
```

Each entry needs a `type` (the import path of a Peewee `Database` class) and a `database` (the connection target). Other keys are passed straight through to the database class.

The connection lifecycle is handled for you: Proper opens connections before routing each request and closes them once the response is sent, for *every* database in the dict.

### Pointing a Model at a Different Database

The existing `BaseModel` is bound to `app.db["main"]` through its `Meta` class. To use the second database, define a sibling base class and have models inherit from it instead:

```python
# models/base.py
import peewee as pw
from proper import ProperModel, scope  # noqa

from ..main import app


db = app.db["main"]


class BaseModel(ProperModel):
    class Meta:
        database = app.db["main"]


class AnalyticsBaseModel(ProperModel):
    class Meta:
        database = app.db["analytics"]
```

Then any model that should live in the analytics database inherits from `AnalyticsBaseModel`:

```python
# models/page_view.py
import peewee as pw

from .base import AnalyticsBaseModel


class PageView(AnalyticsBaseModel):
    path = pw.CharField()
    user_id = pw.IntegerField(null=True)
    viewed_at = pw.DateTimeField(default=pw.utcnow)
```

Everything else - fields, scopes, concerns, CRUD - works exactly like a regular model. Only the underlying connection differs.

:::tip
Don't forget to add the new model to `models/__init__.py` so migrations can detect it, just like any other model.
:::

### Migrations Per Database

Migration files live in `db/<database_name>/`, so each database gets its own folder and its own history. Most `proper db` commands accept a `--db` flag to target one specifically:

```bash
# Generate a migration for the analytics database
proper db create add_page_view --db analytics

# Apply pending migrations for just one database
proper db migrate --db analytics
```

When you run `proper db migrate` without `--db`, Proper applies pending migrations for **every** registered database in turn. That's usually what you want during deployment.

For more on writing migrations, see the [Migrations guide](/docs/migrations).

### Cross-Database Queries

Each database is a separate connection, so SQL can't reach across them. You can't `JOIN` a `Book` (in `main`) against a `PageView` (in `analytics`) - the database engines don't know about each other.

When you need to combine data, query each side and stitch the results together in Python:

```python
top_paths = (
    PageView.select(PageView.path, pw.fn.COUNT(PageView.id).alias("hits"))
    .group_by(PageView.path)
    .order_by(pw.SQL("hits").desc())
    .limit(10)
)

book_paths = {f"/books/{b.id}": b for b in Book.select()}

for row in top_paths:
    book = book_paths.get(row.path)
    if book:
        print(book.title, row.hits)
```

It's not as elegant as a join, but it's the only honest answer when the data lives in two places.

:::warning | Transactions don't span databases
`db.atomic()` only wraps the database it's called on. There's no two-phase commit between separate databases - if you write to `main` and `analytics` in the same request and the second write fails, the first one is *not* rolled back automatically.

If you need that guarantee, design so each unit of work touches only one database, and use a background job (or an idempotent retry) to bridge between them.
:::
