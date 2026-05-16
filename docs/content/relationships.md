---
title: Relationships and Joins
description: |
  Most applications have models that are connected to each other. This guide shows you how to declare those relationships, traverse them from your code, and read them back from the database without doing extra work.
number_headers: true
---

# Relationships and Joins

This guide covers how Proper applications model the connections between data: declaring relationships, following them in code, joining tables, and avoiding the most common performance traps.

After reading this guide, you will know:

- Why relationships exist, and how a foreign key keeps your data consistent.
- How to declare one-to-many, one-to-one, many-to-many, and self-referencing relationships.
- How to traverse a relationship in both directions.
- How to control what happens when a related record is deleted.
- How to write joins, including with multiple foreign keys to the same table.
- How to avoid the N+1 query problem with `prefetch()` and joined `select()`.
- How to count and aggregate across relationships.

For patterns most apps don't reach for on day one - composite primary keys, circular foreign keys, polymorphic relationships, and using more than one database - see the [Advanced Models](/docs/advanced_models) guide.

---

## Why Relationships

Most applications eventually need to connect things to other things. A user writes articles. An article has tags. A comment replies to another comment. You could try to keep everything in one table, but you'd quickly run into trouble:

```python
# Don't do this
class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()
    author_name = pw.CharField()
    author_email = pw.CharField()
    author_bio = pw.TextField()
```

The author's name and bio would be repeated in every one of their articles. If they update their bio, you'd have to update every row. And if two articles spell the name slightly differently, you have no way to know they're the same person.

The fix is to split your data across tables and connect them with **foreign keys**:

```python
class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)
    bio = pw.TextField(default="")


class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()
    author = pw.ForeignKeyField(User, backref="articles", on_delete="CASCADE")
```

Now the author lives in the `user` table, and each article points at them through a single `author_id` column. The database guarantees that `author_id` always refers to a real user - that's the *constraint* in "foreign key constraint". Your code follows the connection in either direction:

```python
article.author       # the user who wrote it
user.articles        # all of this user's articles (a SelectQuery)
```

That's the deal: one declaration on the model, two-way navigation in your code, plus a database that won't let your data drift apart.

:::note | What Peewee gives you, and what it leaves explicit
A single `ForeignKeyField` declaration gets you: the column, the index, the `on_delete` cascade, the forward attribute (`article.author`), and the reverse accessor (`user.articles`).

Anything beyond that - many-to-many, joining across multiple tables, eager loading - is regular query code.
:::

---

## Types of Relationships at a Glance

Before diving in, here's a map of the territory:

| Shape                          | Example                                  | How you declare it                                  |
|--------------------------------|------------------------------------------|-----------------------------------------------------|
| One-to-many                    | A user has many articles                 | `ForeignKeyField` on the "many" side                |
| One-to-one                     | A user has one profile                   | `ForeignKeyField(unique=True)` on the dependent side |
| Many-to-many                   | Articles have many tags, tags have many articles | A through model with two `ForeignKeyField`s |
| Self-referencing               | A comment is a reply to another comment  | `ForeignKeyField("self", ...)`                      |
| Polymorphic (no native support)| A reaction belongs to either an Article or a Comment | Discriminator column + nullable FKs (see [Advanced Models §3](/docs/advanced_models#polymorphic-relationships)) |

Each gets a chapter below. The shape that comes up most often, by far, is one-to-many - start there.

---

## One-to-Many

A one-to-many relationship is when a single record on one side relates to many on the other. A user has many articles; an article has one user. The "many" side gets the foreign key.

:::figure | One user is the author of zero, one, or many articles
![One-to-Many relationship](/assets/images/models/one-to-many.png)
:::

### Declaring a Foreign Key

Use `pw.ForeignKeyField` on the model that does the pointing:

```python
# models/user.py
import peewee as pw

from .base import BaseModel


class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)


# models/article.py
import peewee as pw

from .base import BaseModel
from .user import User


class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()
    author = pw.ForeignKeyField(User, backref="articles", on_delete="CASCADE")
```

Three things happen automatically when you declare a foreign key:

1. A column is added - by default named `<field>_id`. So `author = pw.ForeignKeyField(User, ...)` creates an `author_id` column on the `article` table.
2. An index is created on that column.
3. A reverse accessor is added to the target model, named by the `backref` argument. Above, `User` gains a `.articles` attribute.

The resulting SQL for the `article` table:

```sql
CREATE TABLE "article" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "body" TEXT NOT NULL,
    "author_id" INTEGER NOT NULL,
    FOREIGN KEY ("author_id") REFERENCES "user" ("id") ON DELETE CASCADE
);

CREATE INDEX "article_author_id" ON "article" ("author_id");
```

### Traversing in Both Directions

With the relationship declared, navigation is just attribute access:

```python
# Forward - single instance
article = Article.get_by_id(1)
article.author          # => User instance
article.author.name     # => "Alice"

# Reverse - a SelectQuery (chainable, filterable, scope-able)
user = User.get_by_id(1)
user.articles                                       # all of Alice's articles
user.articles.where(Article.title.contains("Python"))
user.articles.order_by(Article.created_at.desc()).limit(5)
user.articles.count()
```

The key thing to understand: `article.author` returns a *loaded model instance*, but `user.articles` returns a *query* - nothing has been fetched yet. You can keep chaining filters onto it, and it only runs when you iterate it, count it, or call `.first()`.

:::tip
Because the reverse side is a query, your scopes work seamlessly across relationships:

```python
user.articles.published().recent().top(5)
```
:::

### What Happens on Delete: `on_delete`

When the parent record is deleted, what should happen to the children? You decide with `on_delete`:

| Value           | Behavior                                                       |
|-----------------|----------------------------------------------------------------|
| `"CASCADE"`     | Delete the children too                                        |
| `"SET NULL"`    | Set the FK column to `NULL` (requires `null=True` on the FK)   |
| `"RESTRICT"`    | Refuse to delete the parent if children exist                  |
| `"NO ACTION"`   | Same as `RESTRICT` on most databases, but checked at end of transaction |
| (not set)       | Database default - usually `NO ACTION`. **Don't rely on it.**  |

```python
class Article(BaseModel):
    # When the user is deleted, delete their articles
    author = pw.ForeignKeyField(User, backref="articles", on_delete="CASCADE")


class Comment(BaseModel):
    # Keep the comment, but null out the author
    author = pw.ForeignKeyField(User, backref="comments",
                                on_delete="SET NULL", null=True)
    article = pw.ForeignKeyField(Article, backref="comments",
                                 on_delete="CASCADE")
```

:::warning | Always set `on_delete` explicitly
The default behavior depends on the database engine, and a quiet `NO ACTION` somewhere can lead to either unexpected delete failures or - worse - orphaned rows. Pick the behavior you want and write it down.
:::

### Naming the Reverse Accessor

The `backref` argument gives the reverse query its name on the parent model. Pick names that read like English from the parent's point of view:

```python
class Article(BaseModel):
    author = pw.ForeignKeyField(User, backref="articles")
    # Reads as: user.articles
```

If the same model is referenced more than once, each FK needs its own `backref`:

```python
class Article(BaseModel):
    author = pw.ForeignKeyField(User, backref="authored_articles")
    editor = pw.ForeignKeyField(User, backref="edited_articles", null=True)

# user.authored_articles  - articles where this user is the author
# user.edited_articles    - articles where this user is the editor
```

:::tip
If you don't need the reverse accessor at all, set `backref="+"`. Peewee will skip creating it.
:::

### Customizing the Column Name

By default the column is `<field>_id`. Override it with `column_name`:

```python
class Article(BaseModel):
    author = pw.ForeignKeyField(User, backref="articles", column_name="user_id")
```

Useful when you're mapping to a legacy schema, but otherwise resist the urge.

### Generating with the CLI

The model generator understands foreign keys through the `fk-ModelName` shorthand:

```bash
proper g model Article title:str body:text author:fk-User,backref:articles,on_delete:CASCADE
```

This creates `models/article.py`, registers it in `models/__init__.py`, and (with `--migration`) generates the migration file too.

---

## One-to-One

A one-to-one relationship is just a one-to-many with the additional rule that the "many" side is at most one.

:::figure | One user has zero or one profile
![One-to-One relationship](/assets/images/models/one-to-one.png)
:::

You enforce that by adding `unique=True` to the foreign key:

```python
class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)


class Profile(BaseModel):
    user = pw.ForeignKeyField(User, backref="profile",
                              unique=True, on_delete="CASCADE")
    bio = pw.TextField(default="")
    avatar_url = pw.CharField(null=True)
    twitter = pw.CharField(null=True)
```

The unique constraint guarantees that any given `user_id` appears at most once in the `profile` table - exactly one profile per user.

```sql
CREATE UNIQUE INDEX "profile_user_id" ON "profile" ("user_id");
```

### Traversing a One-to-One

Forward navigation is the same as one-to-many:

```python
profile.user        # => User instance
```

Reverse navigation is where one-to-one trips people up. Even though there's at most one related record, `user.profile` is still a `SelectQuery` - Peewee doesn't change its return type based on `unique=True`. You need to materialize it:

```python
user.profile.get()       # raises DoesNotExist if missing
user.profile.first()     # returns None if missing - usually what you want
```

:::tip
If you find yourself writing `.first()` everywhere, add a small helper to your model:

```python
class User(BaseModel):
    @property
    def profile_or_none(self):
        return self.profile.first()
```
:::

### When Not to Use One-to-One

If the dependent model only has a couple of fields and they're always loaded together with the parent, a one-to-one is overkill - just add the columns to the parent table. Keep one-to-one for genuinely independent concerns: optional records, large blobs you don't always want to load, or data that has its own lifecycle.

---

## Many-to-Many

A many-to-many relationship is when records on both sides can relate to many records on the other. Articles have many tags; tags belong to many articles.

:::figure | One article has many tags; one tag belong to many articles
![Many-to-Many relationship](/assets/images/models/many-to-many.png)
:::

Peewee deliberately doesn't have a built-in M:N field by default. You write the join table yourself, because most of the time you eventually want to put extra columns on it (when was the tag added? by whom?), and a hand-written model gives you that for free.

### The Through Model Pattern

Three models - the two ends and the join:

```python
# models/article.py
class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()


# models/tag.py
class Tag(BaseModel):
    name = pw.CharField(unique=True)


# models/article_tag.py
class ArticleTag(BaseModel):
    article = pw.ForeignKeyField(Article, backref="article_tags",
                                 on_delete="CASCADE")
    tag = pw.ForeignKeyField(Tag, backref="tag_articles",
                             on_delete="CASCADE")
    added_at = pw.DateTimeField(default=pw.utcnow)

    class Meta:
        indexes = (
            (("article", "tag"), True),  # Each pair is unique
        )
```

The unique-together index is what stops a tag from being attached to the same article twice.

### Querying Both Sides

There's no shortcut method - you write the join:

```python
# All tags for an article
tags = Tag.select().join(ArticleTag).where(ArticleTag.article == article)

# All articles with a given tag
articles = Article.select().join(ArticleTag).where(ArticleTag.tag == tag)

# All articles tagged "python"
articles = (
    Article.select()
    .join(ArticleTag)
    .join(Tag)
    .where(Tag.name == "python")
)
```

The SQL for the third one:

```sql
SELECT "t1"."id", "t1"."title", "t1"."body"
FROM "article" AS "t1"
INNER JOIN "articletag" AS "t2" ON ("t2"."article_id" = "t1"."id")
INNER JOIN "tag" AS "t3" ON ("t2"."tag_id" = "t3"."id")
WHERE ("t3"."name" = 'python')
```

These join patterns deserve their own chapter - see [Joins](#joins).

### Adding Helper Methods

Repeating join code in every controller gets old fast. Wrap it in a method on the model:

```python
class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()

    @property
    def tags(self):
        return Tag.select().join(ArticleTag).where(ArticleTag.article == self)

    def add_tag(self, tag):
        ArticleTag.get_or_create(article=self, tag=tag)

    def remove_tag(self, tag):
        ArticleTag.delete().where(
            ArticleTag.article == self,
            ArticleTag.tag == tag,
        ).execute()
```

Now controllers can write `article.tags`, `article.add_tag(tag)`, and `article.remove_tag(tag)` without thinking about the join table at all.

### The `ManyToManyField` Shortcut

If you really don't want to write a through model - say, the relationship is purely associative and you'll never need extra columns - Peewee's playhouse offers a shortcut:

```python
from playhouse.fields import ManyToManyField


class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()
    tags = ManyToManyField(Tag, backref="articles")


# Set up the implicit through table after both classes are defined
ArticleTag = Article.tags.get_through_model()
```

This generates a hidden through model for you. You get attribute-style access:

```python
article.tags.add(tag)
article.tags.remove(tag)
list(article.tags)         # all tags
list(tag.articles)         # all articles with this tag
```

:::warning | The trade-off
You no longer have a Python class for the through table, so you can't add columns to it later without rewriting. If there's any chance you'll need *when* the tag was added, *who* added it, or any other per-link metadata, write the through model by hand.
:::

### Choosing Between the Two

| Use the **through model** when…                | Use **`ManyToManyField`** when…                |
|------------------------------------------------|------------------------------------------------|
| You might add per-link columns later           | The relationship is pure association           |
| You want explicit migration control over the join table | You want shorter code                  |
| You want to query the through table directly  | You only ever traverse the relationship       |

When in doubt, write the through model. The extra code is small; the flexibility is large.

---

## Self-Referencing Relationships

Sometimes a model needs to point at itself: Threaded comments (a comment can be a reply to another comment), category trees (a category has subcategories), org charts (an employee reports to another employee), etc.

Use the string `"self"` in place of the target model:

```python
class Comment(BaseModel):
    article = pw.ForeignKeyField(
        Article, backref="comments", on_delete="CASCADE"
    )
    author = pw.ForeignKeyField(
        User, backref="comments", on_delete="CASCADE"
    )
    body = pw.TextField()
    parent = pw.ForeignKeyField(
        "self", backref="replies", null=True, on_delete="CASCADE"
    )
```

A top-level comment has `parent_id = NULL`. A reply has `parent_id` set to the parent comment's id.

```python
top_level = Comment.select().where(Comment.parent.is_null())

for reply in top_level[0].replies:
    print(reply.body)
```

### Walking the Tree

The hard part of self-referencing relationships isn't the declaration - it's querying *all descendants* (or all ancestors) without firing one query per level. SQL has a feature for this called a recursive CTE (Common Table Expression), and Peewee exposes it through the `.cte()` and `.with_cte()` methods.

For shallow trees, it's often simpler to walk `.replies` in Python and accept a few extra queries. Reach for a recursive CTE when the depth is unbounded, or when the tree is large enough that Python-side recursion would issue too many queries.

```python
def descendants(root):
    """All comments below `root`, any depth, in one query."""
    seed = (
        Comment.select(Comment.id, Comment.parent, Comment.body)
        .where(Comment.parent == root.id)
        .cte("descendants", recursive=True,
             columns=("id", "parent_id", "body"))
    )

    Child = Comment.alias()
    step = (
        Child.select(Child.id, Child.parent, Child.body)
        .join(seed, on=(Child.parent == seed.c.id))
    )

    cte = seed.union_all(step)
    return cte.select_from(cte.c.id, cte.c.parent_id, cte.c.body)
```

The result is a query that yields tuples of `(id, parent_id, body)` for every comment underneath `root`. The SQL is one `WITH RECURSIVE ...` statement - no Python recursion, no per-level query.

:::tip
Wrap CTE queries in a method on the model. They're verbose to write and easy to misread; callers shouldn't have to look at them twice.
:::

:::tip | Avoid cycles
Nothing in the database stops you from making `parent_id` form a cycle (`A → B → A`). If your domain shouldn't allow cycles, enforce it in your `save()` method.
:::

---

## Joins

Once your data is split across tables, most non-trivial queries need to combine rows from more than one of them. That's a join.

### What a Join Does

A join takes two tables and a condition, and produces a new virtual table with the columns of both, containing only the row pairs where the condition is true. The condition is usually "the FK on one side equals the primary key on the other".

The two join types you'll use 99% of the time:

- **INNER JOIN**: keep only rows where the condition matches on both sides. Used when you want articles *that have an author* - articles with no author are dropped.
- **LEFT OUTER JOIN**: keep every row from the left side, even when there's no match on the right (right-side columns are `NULL`). Used when you want every article *and* its author if it has one.

::: figure | Visual explanation of joins
![Visual explanation of joins](/assets/images/models/joins.png)
:::

Other types (`RIGHT`, `FULL OUTER`, `CROSS`) exist but rarely come up in application code.

### The Default Join

Calling `.join(Other)` on a query joins the two tables on the foreign key between them. The default is `INNER JOIN`:

```python
articles = (
    Article.select()
    .join(User)
    .where(User.email.endswith("@example.com"))
)
```

The SQL:

```sql
SELECT "t1"."id", "t1"."title", "t1"."body", "t1"."author_id"
FROM "article" AS "t1"
INNER JOIN "user" AS "t2" ON ("t1"."author_id" = "t2"."id")
WHERE ("t2"."email" LIKE '%@example.com')
```

Peewee figures out the join condition by looking at the foreign keys between the two models. If there's exactly one FK from `Article` to `User`, that's what gets used.

### Choosing the Join Type

Pass `join_type` to switch from inner to outer:

```python
# All users, even those who haven't written any articles
query = (
    User.select()
    .join(Article, pw.JOIN.LEFT_OUTER)
)
```

The available constants are `pw.JOIN.INNER`, `pw.JOIN.LEFT_OUTER`, `pw.JOIN.RIGHT_OUTER`, `pw.JOIN.FULL`, `pw.JOIN.FULL_OUTER`, and `pw.JOIN.CROSS`.

### Joining on a Specific Column

When the auto-detected join condition is wrong, or when there's no FK at all, give Peewee an explicit `on=`:

```python
articles = (
    Article.select()
    .join(User, on=(Article.author == User.id))
)
```

`on=` accepts any expression - it's the same kind of clause you put in `.where()`.

### Multiple Foreign Keys to the Same Model

When two foreign keys on a model point to the same target, Peewee can't guess which one to join on. You have to be explicit:

```python
class Article(BaseModel):
    title = pw.CharField()
    body = pw.TextField()
    author = pw.ForeignKeyField(User, backref="authored_articles")
    editor = pw.ForeignKeyField(User, backref="edited_articles", null=True)


# Join on the editor relation, not author
query = (
    Article.select()
    .join(User, on=(Article.editor == User.id))
    .where(User.email == "alice@example.com")
)
```

To load *both* joined users onto the article in one query, alias the second one and use `attr=` on each `.join()` to name where the row data should land:

```python
EditorAlias = User.alias()

query = (
    Article.select(Article, User, EditorAlias)
    .join(User, on=(Article.author == User.id), attr="author")
    .switch(Article)
    .join(EditorAlias, on=(Article.editor == EditorAlias.id), attr="editor")
)

for article in query:
    article.author.name        # populated, no extra query
    article.editor.name        # populated, no extra query
```

The `attr=` argument tells Peewee which Python attribute on the result row should hold the joined model instance. Without it, joining the same model twice would clobber the first one with the second.

### `switch()` - Anchoring the Next Join

When you've joined `A → B` and now want to join `A → C` (not `B → C`), Peewee assumes the next `.join(...)` is from `B`. Use `.switch(A)` to go back:

```python
query = (
    Article.select(Article, User, Tag)
    .join(User)                      # Article → User
    .switch(Article)                 # back to Article
    .join(ArticleTag)                # Article → ArticleTag
    .join(Tag)                       # ArticleTag → Tag
    .where(Tag.name == "python")
)
```

Without `.switch()`, the `ArticleTag` join would try to attach to `User`, which has no FK to it.

### Joining on Arbitrary Fields

`on=` doesn't have to involve a foreign key at all. Sometimes you join on natural keys, denormalized columns, or any expression that produces a boolean:

```python
# Join orders to customers by email, not by an FK
query = (
    Order.select(Order, Customer)
    .join(Customer, on=(Order.customer_email == Customer.email))
)
```

This is rare in well-designed schemas, but invaluable when integrating with legacy data.

### Chaining Multiple Joins

Each `.join()` extends the chain to one more table. The chain reads top-to-bottom:

```python
# Articles → Comments → Users (the comment authors)
query = (
    Article.select(Article, Comment, User)
    .join(Comment)
    .join(User, on=(Comment.author == User.id))
    .where(Article.id == 42)
)
```

For chains longer than two or three joins, give the result some breathing room and consider pulling it into a `@scope`.

### Loading Joined Columns

Here's the most important nuance about joins in Peewee:

:::note
A `.join()` filters your query, but it doesn't *load* the joined columns into your result objects unless you ask for them in `.select()`.
:::

```python
# Joined, but author is NOT loaded
query = Article.select().join(User).where(User.created_at > yesterday)

for article in query:
    article.author.name        # extra query, every iteration
```

To pull the joined data through, list both models in `.select()`:

```python
# Joined and loaded - one query total
query = Article.select(Article, User).join(User)

for article in query:
    article.author.name        # already there
```

This is the cornerstone of avoiding N+1 - see [Eager Loading: Avoiding the N+1 Problem](#eager-loading-avoiding-the-n1-problem).

###0 Subqueries

Sometimes a join is the wrong shape, and a subquery is the right one. A subquery is a `SELECT` used as a value somewhere else.

#### `IN` with a subquery

```python
# Articles whose author is on staff
staff_ids = User.select(User.id).where(User.is_staff == True)
articles = Article.select().where(Article.author.in_(staff_ids))
```

The SQL:

```sql
SELECT "t1"."id", "t1"."title", "t1"."body", "t1"."author_id"
FROM "article" AS "t1"
WHERE ("t1"."author_id" IN (
    SELECT "t2"."id" FROM "user" AS "t2"
    WHERE ("t2"."is_staff" = true)
))
```

#### As a derived value

You can compute a per-row value with a correlated subquery, alias it, and select it alongside the parent:

```python
recent_count = (
    Comment.select(pw.fn.COUNT(Comment.id))
    .where(Comment.article == Article.id, Comment.created_at > yesterday)
    .alias("recent_count")
)

articles = Article.select(Article, recent_count)

for article in articles:
    article.recent_count       # number of recent comments
```

For "is there at least one matching row" checks, an `IN` subquery is usually cleaner; reach for `pw.fn.EXISTS(subquery)` only when the subquery is independently shaped (e.g. references multiple outer columns).

---

## Eager Loading: Avoiding the N+1 Problem

The single most common performance bug in ORM-backed applications looks like this:

```python
# Looks innocent. Isn't.
for article in Article.select():
    print(article.title, "by", article.author.name)
```

This issues **one** query to load articles, then **one more** query for each article to load its author. With 50 articles, that's 51 queries. With 5,000, you've got a problem. This is the N+1 problem.

Proper logs every SQL statement in development mode, so you can see this happening in your terminal. When you spot a wall of nearly-identical queries, you've found an N+1.

There are two ways to fix it.

### Strategy A: Join + Select (one query, flat result)

When the relationship is "to one" - the article belongs to a user, the comment belongs to an article - join the table and pull its columns through `.select()`:

```python
articles = Article.select(Article, User).join(User)

for article in articles:
    print(article.title, "by", article.author.name)   # no extra query
```

One query. Each row carries all the article and author columns. This is what other ORMs sometimes call `select_related` or `includes`.

### Strategy B: `prefetch` (two queries, joined in Python)

When the relationship is "to many" - has many comments, has many tags - joining produces a Cartesian explosion: one row per child for every parent. Instead, run two queries and let Peewee stitch the results together:

```python
articles = Article.select()
comments = Comment.select()

for article in pw.prefetch(articles, comments):
    print(article.title, len(article.comments))   # no extra queries
```

`prefetch()` runs the article query, then runs the comment query restricted to those articles' ids, then attaches each comment to its parent in Python. The prefetched children replace the regular backref attribute: before the call, `article.comments` is a lazy `SelectQuery`; after `prefetch()` returns, it's a plain `list` of fully-loaded `Comment` instances.

:::warning
Because `article.comments` becomes a `list` after prefetching, methods like `.where(...)` or `.count()` no longer work on it - those belong to the query, not the list. Filter the comment query *before* passing it into `prefetch()`:

```python
recent = Comment.select().where(Comment.created_at > yesterday)
for article in pw.prefetch(Article.select(), recent):
    article.comments    # only the recent ones, as a list
```
:::

You can prefetch arbitrarily deep:

```python
articles = Article.select()
comments = Comment.select()
users    = User.select()

# Three queries: articles, comments, comment authors
results = pw.prefetch(articles, comments, users)
```

### Picking Between Them

A useful rule of thumb:

| Relationship                       | Use                              |
|------------------------------------|----------------------------------|
| "Belongs to" (the "one" side)      | `.join().select(A, B)`           |
| "Has many" (the "many" side)       | `prefetch(A, B)`                 |
| "Has one"                          | Either works; `.join()` is simpler |
| Many-to-many                       | `prefetch(A, ThroughModel, B)`   |

The reason: a join multiplies rows. Joining articles to their comments returns one row per comment (so a 100-article page with 20 comments each is 2,000 rows). Joining articles to their author returns one row per article. The first wastes bandwidth; the second doesn't.

### Combining: Filter with Join, Load with Prefetch

You can use both in the same query - `.join()` to filter, `prefetch()` to load:

```python
# Articles by staff users, with their comments preloaded
staff_articles = (
    Article.select()
    .join(User)
    .where(User.is_staff == True)
)

results = pw.prefetch(staff_articles, Comment.select())
```

The join narrows the article set; the prefetch attaches the comments. Two queries, no N+1.

:::tip | Watch the SQL
The fastest way to spot N+1 problems is to keep an eye on the dev server's query log when you're loading a page. If you see the same `SELECT ... WHERE id = ?` shape repeating, you have one. Fix it with one of the two strategies above.
:::

---

## Aggregations Across Relationships

Counting, summing, and averaging across a relationship is a thin wrapper over SQL aggregate functions. The pattern is always: `.select()` what you want plus the aggregate, `.join()` if needed, `.group_by()` the parent.

### Counting Children

```python
# How many articles each user has written
query = (
    User.select(User, pw.fn.COUNT(Article.id).alias("article_count"))
    .join(Article, pw.JOIN.LEFT_OUTER)
    .group_by(User.id)
)

for user in query:
    print(user.name, user.article_count)
```

The `LEFT_OUTER` join is what makes users with zero articles still show up (with `article_count = 0`). An inner join would silently drop them.

### Wrapping Aggregates as Scopes

If you reach for a counted query more than once, extract it:

```python
class User(BaseModel):
    name = pw.CharField()
    email = pw.CharField(unique=True)

    @scope
    def with_article_count(query):
        return (
            query.select(User, pw.fn.COUNT(Article.id).alias("article_count"))
            .join(Article, pw.JOIN.LEFT_OUTER)
            .group_by(User.id)
        )
```

Now controllers read like this:

```python
users = User.select().with_article_count().order_by(pw.SQL("article_count").desc())
```

### Filtering on Aggregates: `having()`

`WHERE` filters rows before aggregation; `HAVING` filters them after. Use `.having()` when the condition involves the aggregate value itself:

```python
# Only users who have written at least 5 articles
prolific = (
    User.select(User, pw.fn.COUNT(Article.id).alias("article_count"))
    .join(Article)
    .group_by(User.id)
    .having(pw.fn.COUNT(Article.id) >= 5)
)
```

### Other Aggregates

`pw.fn.SUM`, `pw.fn.AVG`, `pw.fn.MIN`, and `pw.fn.MAX` all work the same way. Always `alias()` them so you can read the value off the result row.

---

## Tips, Tricks, and Warnings

A grab-bag of things that come up after you've used relationships for a while.

### Always set `on_delete` explicitly

The default behavior depends on the database engine. Pick the right value (`CASCADE`, `SET NULL`, or `RESTRICT`) and write it down. A relationship without `on_delete` is a bet that you, or whoever inherits this code, will remember the default. Don't make that bet.

### `backref` returns a query, not a list

Every time you access `user.articles`, you get a fresh `SelectQuery`. Iterating it twice runs the query twice:

```python
for a in user.articles: print(a.title)   # query 1
for a in user.articles: print(a.id)      # query 2 - same results
```

If you need to iterate the same set more than once, materialize it first:

```python
articles = list(user.articles)
for a in articles: ...
for a in articles: ...
```

The exception is after `pw.prefetch()` - the backref attribute is replaced with a real `list`, so iteration is free but query methods like `.where()` won't work on it. See [Strategy B: `prefetch` (two queries, joined in Python)](#strategy-b-prefetch-two-queries-joined-in-python).

### Watch for `backref` collisions

Two models referencing the same parent must use different `backref` names:

```python
class Article(BaseModel):
    author = pw.ForeignKeyField(User, backref="articles")  # ok

class Comment(BaseModel):
    user = pw.ForeignKeyField(User, backref="articles")    # collision
```

The second declaration silently overrides the first. Pick distinct names - `comments`, `authored_articles`, `assigned_tickets`.

### Adding an FK to a populated table

A `NOT NULL` foreign key needs a value for every existing row. When you add one to a table that already has data, the migration will fail unless either:

- The column is `null=True`, or
- You provide a `default`.

For more, see the [Migrations guide](/docs/migrations).

### Index your FK + filter combinations

FK columns are indexed automatically, but most real queries filter on more than just the FK:

```python
Article.select().where(Article.author == user, Article.published == True)
```

A composite index on `(author_id, published)` will be much faster than the bare FK index. See [Models §7.2](/docs/models#composite-indexes).

### You cannot join across databases

If `Article` lives in your `main` database and `PageView` lives in `analytics`, no join in any framework can put them in the same query - the database engines don't talk to each other. Query each side and combine in Python. See [Advanced Models §4.4](/docs/advanced_models#cross-database-queries).

### Test relationships against real tables

The test fixture in `conftest.py` runs every test inside a transaction that rolls back when the test exits. That's fast enough that you should always test relationships with real `.create()` calls and real queries, not mocks. A mocked `backref` doesn't behave like a real `SelectQuery`, and the differences will bite you.

```python
def test_user_articles_returns_only_their_articles():
    alice = User.create(name="Alice", email="alice@example.com")
    bob   = User.create(name="Bob",   email="bob@example.com")
    Article.create(title="A1", body="...", author=alice)
    Article.create(title="A2", body="...", author=alice)
    Article.create(title="B1", body="...", author=bob)

    assert alice.articles.count() == 2
    assert bob.articles.count() == 1
```

---

## Reference Card

A quick lookup for the syntax bits you'll forget the most.

### `ForeignKeyField` options

| Option            | What it does                                           |
|-------------------|--------------------------------------------------------|
| `backref="..."`   | Name of the reverse accessor on the target model       |
| `backref="+"`     | Don't create a reverse accessor at all                 |
| `on_delete=...`   | `"CASCADE"`, `"SET NULL"`, `"RESTRICT"`, `"NO ACTION"` |
| `unique=True`     | Makes it a one-to-one                                  |
| `null=True`       | The FK column is nullable                              |
| `column_name=...` | Override the default `<field>_id` column name          |
| `field=...`       | Reference a non-PK column on the target (rare)         |

### `pw.JOIN` constants

`INNER`, `LEFT_OUTER`, `RIGHT_OUTER`, `FULL`, `FULL_OUTER`, `CROSS`.

### Eager-loading checklist

| Shape                      | Tool                                          |
|----------------------------|-----------------------------------------------|
| "Belongs to" (one side)    | `.select(A, B).join(B)`                       |
| "Has many"                 | `pw.prefetch(A, B)`                           |
| Many-to-many               | `pw.prefetch(A, Through, B)`                  |
| Nested                     | `pw.prefetch(A, B, C, ...)`                   |
| Filter + load              | `.join()` for filter, `prefetch()` for load   |

### Useful imports

```python
import peewee as pw
from playhouse.fields import ManyToManyField
```
