---
title: Caching
description: |
  How caching works in Proper. Covers the SQLite and Redis cache stores, low-level get/set, fragment caching with the `{% cache %}` tag, Russian doll caching, HTTP conditional requests, and how the cache behaves in development and tests.
number_headers: true
---

# Caching

Caching is the art of doing the same expensive work only once. Some pages are slow because they aggregate data from many tables; others are slow because they render a large template; others still get hit by the same client over and over, asking the server to recompute a page that hasn't changed. In all three cases, the answer is to keep the result somewhere fast and serve it from there until the underlying data moves.

Proper gives you three cooperating ways to do that:

- **A server-side cache store.** A key-value store at `app.cache`, backed by SQLite or Redis. Use it for anything expensive to compute - aggregated stats, third-party API responses, rendered fragments.
- **Fragment caching.** A `{% cache %}` template tag that wraps a block of markup and stores the rendered HTML keyed off whatever you pass in - a string, a model object, a collection.
- **HTTP caching.** `ETag` and `Last-Modified` headers that let the browser skip a render entirely when the page hasn't changed. The work shifts from "render and send" to "answer 304 Not Modified."

After reading this guide, you will know:

- How to configure a cache store per environment, and which backend belongs in development, tests, and production.
- How to memoize expensive function results and counters in `app.cache`.
- How to cache fragments of templates, and how Russian doll caching lets nested fragments invalidate independently.
- How to turn an action into a conditional GET so repeat visitors use their browser's cache instead of having to re-render.

This guide does not cover query caching at the ORM level and only briefly touches on HTTP caching - the full conditional-GET reference lives in the [Controllers Advanced guide, section 5](/docs/controllers_advanced#http-caching-with-fresh_when).

---

## What is caching?

A *cache* is a fast store you check before doing slow work. The pattern is always the same: build a key that identifies the result, look it up, do the work and store it on a miss, return what's stored on a hit. The only interesting decisions are *what to cache*, *what to key it by*, and *when to invalidate*.

Proper's caching surface has three layers that pair with the three places work happens:

Layer              | Where it sits                | What it stores                          | When to reach for it
-------------------|------------------------------|-----------------------------------------|--------------------------------------------------------
Cache store        | `app.cache` (server-side)    | Any pickled Python value                | Expensive computations, counters, batched API responses
Fragment caching   | `{% cache %}` in templates   | Rendered HTML                           | Slow templates, sidebars, lists with stable items
HTTP caching       | `ETag` / `Last-Modified`     | Nothing - the *browser* keeps the body  | Same client revisits the same URL between updates

All three share one principle: a cache only helps if the **key changes when the data does**. Most of the design effort in caching is choosing keys that invalidate themselves automatically when the underlying data moves. Both fragment caching and HTTP caching lean on a model's `updated_at` timestamp to do exactly that - we'll come back to it in [section 4](#fragment-caching) and [section 6](#http-caching).

---

## Configuration

Cache settings live in `config/storage.py` under the `CACHE` key. A freshly generated application carries per-environment defaults:

```python {title="myapp/config/storage.py"}
import os

env = os.getenv("APP_ENV", "dev")

# Development - in-memory SQLite, fast, cleared on restart
CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": ":memory:",
}

if env == "test":
    CACHE = {
        "type": "proper.cache.NoCache",
    }

if env == "prod":
    CACHE = {
        "type": "proper.cache.SqliteCache",
        "database": "storage/cache.sqlite3",
    }
```

The `type` key names the backend class; every other key is passed to its constructor. That's the only switch you ever need - the same code calls `app.cache.set(...)` regardless of where the bytes go.

### Backends

Three backends ship with the framework:

Backend       | Import path                | Use it for
--------------|----------------------------|-----------------------------------------------------------
`SqliteCache` | `proper.cache.SqliteCache` | Default in dev and small/medium production deployments
`RedisCache`  | `proper.cache.RedisCache`  | Production when you already run Redis, or need network access from multiple processes
`NoCache`     | `proper.cache.NoCache`     | Tests, and any environment where caching must be a no-op

There is no separate "memory" backend. `SqliteCache` with `":memory:"` as its database behaves like one: it never touches disk, it's process-local, and it's cleared when the process restarts. That's the default in development.

### `SqliteCache`

```python
CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": "storage/cache.sqlite3",
    "expires_in": 60 * 60 * 24,   # default TTL: 1 day
    "timeout": 5,                 # SQLite connection timeout in seconds
}
```

Option       | Default              | Description
------------ | -------------------- | ----------------------------------------------------------------
`database`   | (required)           | Path to the SQLite file, or `":memory:"` for an in-memory cache
`expires_in` | `172800` (2 days)    | Default TTL in seconds for cached values
`serializer` | `None`               | Custom serializer (uses pickle by default)
`timeout`    | `5`                  | SQLite connection timeout in seconds

Any additional keys are passed as SQLite pragmas. The cache always opens its database in WAL mode so reads and writes can happen concurrently - a `set()` from one request doesn't block a `get()` from another.

### `RedisCache`

Redis is an optional dependency. The `redis` package is only imported if you actually use this backend. Install it with:

```bash
$ uv add redis
```

```python
CACHE = {
    "type": "proper.cache.RedisCache",
    "url": "redis://localhost:6379/0",
    "expires_in": 60 * 60 * 24,
}
```

Option       | Default                       | Description
------------ | ----------------------------- | ----------------------------------------------------------------
`url`        | `"redis://localhost:6379/0"`  | Redis connection URL
`expires_in` | `172800` (2 days)             | Default TTL in seconds for cached values
`serializer` | `None`                        | Custom serializer (uses pickle by default)

Any other keys are forwarded to `redis.from_url()`, so options like `socket_timeout` or `ssl=True` work as you'd expect.

Redis expires keys natively. The `delete_expired()` method is a no-op for this backend; you don't have to schedule cleanup.

### `NoCache`

`NoCache` is the null object: every `set` is dropped, every `get` returns `None`, `increment` returns `0`. The same code that exercises the cache in production runs cleanly under `NoCache`, which is what makes it the right default in tests - assertions stay deterministic without anyone managing cache state between cases.

In production you almost never want this. If you've turned off caching to debug a problem, prefer the in-memory SQLite cache and call `app.cache.clear()` instead.

### What happens if `CACHE` is unset

If you don't define `CACHE` at all, Proper falls back to `NoCache`. The application still boots; everything that touches the cache continues to work; nothing is actually cached. This is intentional - a missing config should never crash an app over a non-essential feature - but it means production performance will be quietly bad. The generated `config/storage.py` always sets `CACHE` explicitly so you notice.

---

## Low-Level Caching

The cache store is a key-value dictionary with a TTL. You reach it through `app.cache` from a controller, or via `current.app.cache` from anywhere else:

```python
from proper import current

cache = current.app.cache

# Store a value (uses the default TTL)
cache.set("stats:daily", computed_stats)

# Store with a custom TTL
cache.set("stats:daily", computed_stats, expires_in=3600)

# Retrieve a value (returns None on miss or expired)
stats = cache.get("stats:daily")

# Delete a value
cache.delete("stats:daily")
```

Values are pickled on the way in and unpickled on the way out, so you can store any Python object - a list, a dataclass, a Peewee model instance. The TTL is set at write time: every `set` computes an `expires_at = now + expires_in`. On `get`, if `expires_at` has passed, the entry is deleted and `None` is returned.

### `get_or_set`

The common pattern - "give me the cached value, but compute and store it if it's missing" - is one call. Pass a callable; it's only invoked on a miss:

```python
stats = cache.get_or_set(
    "stats:daily",
    compute_stats, # callable
    expires_in=3600,
)
```

This is the memoization primitive most caching code reaches for. The callable wraps the expensive work; the framework handles the lookup, the recompute, the store.

### Preventing the thundering herd

When a popular key expires and many requests arrive at the same moment, all of them see a cache miss, all of them recompute the same value, and your database briefly serves as if the cache wasn't there. This is the *thundering herd* problem.

`race_condition_ttl` prevents it. When the first request sees the expired key, the cache extends the stale entry's TTL by the race window. Subsequent requests during that window find the (extended) old value and return it immediately, while the first request alone does the recompute:

```python
stats = cache.get_or_set(
    "stats:daily",
    lambda: Stats.compute(),
    # logical TTL: 5 minutes
    expires_in=300,
    # serve stale for up to 10s during recompute
    race_condition_ttl=10,
)
```

The trade-off is honest: for `race_condition_ttl` seconds after expiry, some clients see the old value. That's almost always better than the alternative (everyone recomputing in parallel and your database falling over). Pick a window that's longer than the recompute takes - 5 to 30 seconds is typical for "expensive but not slow" work.

### Counters: `increment` and `decrement`

When the value is a number, you want atomic update, not read-modify-write. `increment` and `decrement` do this for you:

```python
# Increment by 1 (the default)
views = cache.increment("page:views:42")

# Increment by a custom amount
bytes_sent = cache.increment("api:bytes:user-7", 1024)

# With a custom TTL
cache.increment("page:views:42", expires_in=3600)

# Decrement (returns the new value)
remaining = cache.decrement("quota:remaining:user-7", 5)
```

If the key doesn't exist or has expired, the counter starts from the given value. Under the hood, the SQLite backend wraps the read-modify-write in a transaction; the Redis backend uses an optimistic `WATCH`/`MULTI` loop. Both are safe to call from concurrent requests.

This is the primitive the rate limiter uses internally - see [Controllers Advanced, section 3](/docs/controllers_advanced#rate-limiting-the-hard-cases).

### Batch operations

`read_multi` and `write_multi` operate on many keys in one round-trip. With Redis, they map to `MGET` and a pipelined sequence of `SET` commands; with SQLite, they collapse to a single `WHERE key IN (...)` query and a single transaction. Either way, this is dramatically faster than a loop over `get` / `set` when the keys count more than a handful:

```python
# Read - returns a dict of hits only (misses are absent)
results = cache.read_multi("user:1", "user:2", "user:3")
# => {"user:1": ..., "user:3": ...}

# Write
cache.write_multi(
    {"user:1": user1_data, "user:2": user2_data, "user:3": user3_data},
    expires_in=3600,
)
```

Reach for these when you're warming a cache, hydrating a batch of objects, or invalidating a known set of keys at once.

### `clear` and `delete_expired`

`clear()` wipes every entry. Use it sparingly - in a production app it's almost always a sign that something has gone wrong - but it's handy in scripts and as a "reset" between test cases:

```python
cache.clear()
```

`delete_expired()` removes already-expired rows. The SQLite backend does *lazy* expiration - an expired key is only physically deleted when something tries to read it - so a long-running app accumulates dead rows until they're touched again. Calling `delete_expired()` from a scheduled task once a day keeps the table small:

```python
@app.queue.periodic_task(crontab(hour="3"))
def prune_cache():
    current.app.cache.delete_expired()
```

The Redis backend handles expiration natively; `delete_expired()` is a no-op there and you can leave the scheduled task out.

---

## Fragment Caching

Fragment caching stores rendered HTML blocks so the template engine doesn't have to render them again on the next request. The `{% cache %}` tag wraps the slow part of a template; the first render stores the HTML in `app.cache`, every subsequent render reads it back:

```html+jinja
{% cache "sidebar" %}
  ... expensive rendering ...
{% endcache %}
```

That's the whole API for the simple case. The first time this block renders, the engine evaluates its body, stores the result under the key `"sidebar"`, and returns it. Every subsequent render fetches the stored HTML directly - no template parsing, no database queries inside the block, nothing.

The full syntax has four arguments. Only the first is required:

```html+jinja
{% cache key [, expires_in=seconds] [, version=string] [, race_condition_ttl=seconds] %}
  ...
{% endcache %}
```

Argument             | Type                          | Description
-------------------- | ----------------------------- | -----------------------------
`key`                | string, object, or iterable   | What the fragment is keyed on. See [section 4.1](#caching-by-string-object-or-collection).
`expires_in`         | int                           | TTL in seconds. Defaults to the backend's default (2 days).
`version`            | string or int                 | Manual version tag appended to the key. Bumping this invalidates the entry.
`race_condition_ttl` | int                           | Seconds to extend a stale entry while one request re-renders. See [section 4.3](#race-conditions-in-fragments).

### Caching by string, object, or collection

The first argument is what makes fragment caching feel like part of the data model rather than a separate concern. It can be any of three things, and Proper builds the cache key differently for each:

**A string** is used as the key directly:

```html+jinja
{% cache "sidebar" %}
  ...
{% endcache %}
```

Good for fragments that aren't tied to a specific record - the marketing footer, a global announcement bar, the sidebar of a generic page. You'll usually set `expires_in` to control when these refresh, because nothing in the key changes on its own.

**A model object** generates a key from the object's class name, ID, and `updated_at` timestamp:

```html+jinja
{% cache card %}
  <div class="card">
    <h2>{{ card.title }}</h2>
    <p>{{ card.body }}</p>
  </div>
{% endcache %}
```

This is the powerful one. The key looks like `view:1735689600.0/card/42`, where the floating-point number is the `updated_at` timestamp. When the card is saved, `updated_at` changes, which changes the key, which means the next render is a *miss* and re-renders the block. The old entry stays around until it expires (or `delete_expired` cleans it up), but nobody reads from it because nobody can build its key anymore. You get automatic invalidation without ever calling `cache.delete`.

This pattern is sometimes called *key-based expiration* or "the cache is its own invalidation strategy." It works because Proper's `BaseModel` ships an `updated_at` column out of the box; if you're caching objects that don't have one, set `expires_in` explicitly or supply a `version`.

**A collection** (a list, tuple, or any iterable of model objects) generates a key from the class name, the count, and the maximum `updated_at` across the collection:

```html+jinja
{% cache cards %}
  {% for card in cards %}
    <div class="card">{{ card.title }}</div>
  {% endfor %}
{% endcache %}
```

The fragment invalidates when any object in the collection is added, removed, or updated. The "count" component handles add/remove (a different count means a different key); the "max updated_at" handles updates. A Peewee `SelectQuery` is iterable, so the usual `Card.select().order_by(...)` shape works directly - just remember that iterating the query for the key forces it to execute, which is usually what you want anyway.

### Expiration and versioning

For fragments keyed on a string, `expires_in` is how you control freshness:

```html+jinja
{% cache "trending", expires_in=300 %}
  ... refreshed every 5 minutes ...
{% endcache %}
```

For fragments keyed on a model or collection, the `updated_at` mechanism already handles data-driven invalidation, so `expires_in` is usually just a safety net - "even if I missed something, refresh this within a day."

`version` is the manual override. When the *template* changes but the data hasn't, the model's `updated_at` doesn't move, and the old (now-misrendered) HTML stays in the cache. Bumping the version forces a re-render:

```html+jinja
{% cache card, version="v2" %}
  ... new layout, even if the card hasn't been saved ...
{% endcache %}
```

In practice you reach for `version` rarely, after a redesign. The everyday workflow leans on `updated_at`.

### Race conditions in fragments

The same `race_condition_ttl` parameter from [section 3.2](#preventing-the-thundering-herd) applies to `{% cache %}`. When a heavily-trafficked fragment expires, you don't want every concurrent request to re-render it:

```html+jinja
{% cache "trending", expires_in=300, race_condition_ttl=10 %}
  ... expensive rendering ...
{% endcache %}
```

While the first request re-renders, the cache continues serving the stale HTML to everyone else for up to 10 seconds. Pick a window that's at least as long as the slowest plausible render time for the block.

---

## Russian Doll Caching

*Russian doll caching* is a technique that nests cached fragments inside other cached fragments. When something deep inside changes, only it and its enclosing fragments have to re-render; sibling fragments stay cached.

The shape, in a template:

```html+jinja
{% cache post %}
  <article>
    <h1>{{ post.title }}</h1>
    {% for comment in post.comments %}
      {% cache comment %}
        <div class="comment">
          {{ comment.body }}
        </div>
      {% endcache %}
    {% endfor %}
  </article>
{% endcache %}
```

If you edit a single comment, you'd like:

- That comment's fragment to invalidate (its `updated_at` changed - it does).
- The post's fragment to invalidate too (so the updated comment is rendered into the outer markup).
- Every *other* comment's fragment to stay cached (they didn't change).

The first part works by itself; the third works by itself; the second one is the catch. The post's `updated_at` didn't change when the comment did, so the outer `{% cache post %}` keeps serving the old HTML - which still contains the old comment's body baked in.

### The `touches` pattern

The fix is to bump the parent's `updated_at` whenever a child changes. Proper's blueprint ships a `RussianDollCached` mixin that does exactly this. It lives at `models/concerns/russian_doll_cached.py` in your application:

```python {title="models/comment.py"}
import peewee as pw

from .concerns.russian_doll_cached import RussianDollCached
from .post import Post


class Comment(RussianDollCached):
    post = pw.ForeignKeyField(Post, backref="comments")
    body = pw.TextField()

    touches = ("post",)
```

`touches` is a tuple of foreign-key field names. When a `Comment` is saved or deleted, the mixin walks each name, finds the related record, and calls `touch()` on it - which bumps that record's `updated_at`. The post's cache key changes; the outer `{% cache post %}` re-renders; the inner `{% cache comment %}` blocks for unchanged comments are still cached and served from the store.

### Cascading touches

`touches` cascades. If replies touch comments, and comments touch posts, saving a reply walks the whole chain:

```python {title="models/reply.py"}
import peewee as pw

from .concerns.russian_doll_cached import RussianDollCached
from .comment import Comment


class Reply(RussianDollCached):
    comment = pw.ForeignKeyField(Comment, backref="replies")
    body = pw.TextField()

    touches = ("comment",)
```

A `Reply.save()` bumps the comment's `updated_at`, which (via the comment's own `touches`) bumps the post's `updated_at`. All three layers invalidate; everything else stays cached.

### Manual `touch()`

You can also bump a record's timestamp yourself, without going through a save:

```python
post.touch()
```

That's useful when something external changes the post's effective freshness - a moderator approves it, an attached image finishes processing, a related record outside the `touches` chain is updated. `touch()` updates the row's `updated_at` and propagates to anything declared in its own `touches`.

### When to reach for it

Russian doll caching pays off when:

- A page renders many items of the same shape (comments, line items, list rows).
- Most renders touch most items unchanged - a single new comment shouldn't invalidate the other 200.
- The per-item template is non-trivial enough to be worth caching individually.

It doesn't pay off when:

- The page has one or two big sections (a single big `{% cache %}` block is simpler).
- The data changes constantly (every save invalidates the whole tree anyway - you're paying the bookkeeping cost for nothing).
- The items already render in microseconds (cache lookup overhead is real; not everything wins).

---

## HTTP Caching

The cache store and fragment caching both keep work *on the server*. HTTP caching lets the work disappear entirely: when the page hasn't changed, the browser uses what it already has and the server returns `304 Not Modified` with no body.

The mechanism is the **conditional GET**. Every response carries either an `ETag` (a fingerprint of the body), a `Last-Modified` header (the timestamp of the latest change), or both. The browser sends those values back on the next request as `If-None-Match` and `If-Modified-Since`. If the values still match what the server would produce, the server skips the body and answers `304`.

### `fresh_when`

The controller-level helper is `self.response.fresh_when`. Pass a model object with an `updated_at` attribute and Proper handles both headers:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.response.fresh_when(self.card)
```

After the action runs, Proper checks the request's `If-None-Match` / `If-Modified-Since`. If the cached version on the client matches, the response body is discarded and the status set to `304`. If not, the rendered HTML is sent as normal.

Collections work the same way - Proper picks the maximum `updated_at` across them - and a `strong=True` / `public=True` option pair lets you tweak the ETag style and the `Cache-Control` directive. The full reference is in [Controllers Advanced, section 5](/docs/controllers_advanced#http-caching-with-fresh_when), which also covers when to reach for `fresh_when` and when not to.

### `Cache-Control` directly

For custom strategies that don't fit `fresh_when`, set `Cache-Control` on the response yourself:

```python
self.response.set_cache_control("max-age=3600", "public")
self.response.set_cache_control("max-age=0", "private", "must-revalidate")
self.response.set_cache_control("max-age=31536000", "public", "immutable")
```

Each argument is a single directive; they're joined with commas in the header. Pass zero arguments to delete the header entirely.

### Static assets

Static files are cached automatically. Fingerprinted asset URLs (the ones with a hash in the filename, like `/assets/css/app-a1b2c3d4.css`) are served with `Cache-Control: max-age=31536000, public, immutable` - one year, with no revalidation. Non-fingerprinted assets get `max-age=0, public, must-revalidate` and support `If-Modified-Since`. The [Static Assets guide, section 7](/docs/assets#cache-control-headers) covers the headers in detail, and [section 6](/docs/assets#filename-fingerprinting) explains how the fingerprint URL is built.

---

## Cache Keys

When you pass a model or collection to `{% cache %}`, Proper turns it into a string key via a small set of helpers. The same helpers are exposed for application code that wants to build cache keys the same way:

```python
from proper.cache import key_for, key_for_object, key_for_collection
```

You won't reach for them often - the `{% cache %}` tag and the controller helpers cover the common cases - but they're useful when you want manual control over a key in `cache.get_or_set`, or when you're building cache keys for HTTP responses outside the `fresh_when` shape.

`key_for` is the dispatcher. It looks at the type of the argument and delegates:

```python
key_for("view", "sidebar")          # => "sidebar"
key_for("view", card)               # => "view:1735689600.0/card/42"
key_for("view", cards)              # => "view:1735689600.0/card/col/5"
```

- **String** - returned lowercased. The `prefix` and `version` arguments are ignored.
- **Object** - delegates to `key_for_object`.
- **List or tuple** - delegates to `key_for_collection`.
- **Dict, bytes, bytearray** - raises `ValueError` (these are ambiguous shapes).

`key_for_object` formats one model:

```python
key_for_object("view", card)        # => "view:1735689600.0/card/42"
```

The format is `"{prefix}:{version}/{class}/{id}"`, all lowercased. The version defaults to the timestamp of the object's `updated_at`. Pass `version=...` to override.

`key_for_collection` formats an iterable:

```python
key_for_collection("view", cards)   # => "view:1735689600.0/card/col/5"
```

The format is `"{prefix}:{version}/{class}/col/{count}"`. The version defaults to the maximum `updated_at` across the collection.

---

## Custom Cache Backends

If the three bundled backends don't fit - you run Memcached, you want to layer in a tiered cache, you need to talk to a managed service with its own client - subclass `BaseCache` and implement the protocol:

```python {title="myapp/cache/memcached_cache.py"}
import memcache

from proper.cache import BaseCache


class MemcachedCache(BaseCache):
    def __init__(self, servers, *, expires_in=172800, serializer=None):
        super().__init__(serializer=serializer)
        self.expires_in = expires_in
        self.client = memcache.Client(servers)

    def set(self, key, value, *, expires_in=None):
        ttl = expires_in if expires_in is not None else self.expires_in
        self.client.set(key, self.serialize(value), time=ttl)

    def get(self, key):
        data = self.client.get(key)
        return self.deserialize(data) if data is not None else None

    def increment(self, key, value=1, *, expires_in=None):
        result = self.client.incr(key, value)
        if result is None:
            self.set(key, value, expires_in=expires_in)
            return value
        return result

    def decrement(self, key, value=1, *, expires_in=None):
        return self.increment(key, -value, expires_in=expires_in)

    def delete(self, key):
        self.client.delete(key)

    def clear(self):
        self.client.flush_all()
```

`BaseCache` provides default implementations for `get_or_set`, `read_multi`, `write_multi`, and `delete_expired` in terms of the methods above. Override any of them when the underlying store has a faster way (a native `MGET`, native counters, a pipelined batch write) - both `SqliteCache` and `RedisCache` do exactly that.

Register the backend by pointing `CACHE["type"]` at the full dotted path:

```python
CACHE = {
    "type": "myapp.cache.memcached_cache.MemcachedCache",
    "servers": ["127.0.0.1:11211"],
}
```

Every key in the dict except `type` is forwarded as a keyword argument to the constructor.

---

## Caching in Development and Tests

The three environments call for different strategies, and the generated `config/storage.py` switches between them automatically. The shape of the code never changes; only the backend underneath.

### Development

Default: `SqliteCache(":memory:")`. The cache is fast (no disk, no network), shared across threads within the process, and disappears on restart. That last property is what you usually want in development - flipping the dev server restarts everything, including the cache, so you never end up debugging "why is this stale page still showing."

If you want cache that *survives* restarts during development (because you're working on something where regenerating the cache is slow), point it at a file:

```python
CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": "tmp/dev-cache.sqlite3",
}
```

Delete the file to wipe the cache; restart the server to reload it.

### Tests

Default: `NoCache`. Every `set` is a no-op, every `get` returns `None`. Code that goes through the cache still runs - `cache.get_or_set` calls the callable every time, exactly as it would on a miss - but no state crosses test boundaries. You almost never need a fixture for "clear the cache."

If a specific test cares about cache behavior (caching counters, race conditions, the actual hit/miss flow), swap to in-memory SQLite for that test:

```python
def test_increment_persists_across_calls(app):
    app.cache = SqliteCache(":memory:")
    app.cache.increment("counter")
    app.cache.increment("counter")
    assert app.cache.get("counter") == 2
```

Don't forget to reset it - in practice, scope a fixture to the test that needs it.

### Production

Default: `SqliteCache("storage/cache.sqlite3")`. A SQLite file at the project root works fine for single-process and small multi-process deployments - SQLite's WAL mode handles concurrent reads while one writer updates, and the cache database is small enough that it stays hot in the OS page cache.

When you need a cache that's accessible from multiple machines, switch to Redis. The change is one config block; nothing else moves:

```python
if env == "prod":
    CACHE = {
        "type": "proper.cache.RedisCache",
        "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    }
```

If you use `SqliteCache` in production, schedule `cache.delete_expired()` to run periodically (see [section 3.5](#clear-and-delete_expired)). Without it, expired rows stay on disk until they're touched again on read.

---

## What's next

Caching connects to several other parts of Proper. A few places to go from here:

- [Controllers Advanced, section 6](/docs/controllers_advanced#http-caching-with-fresh_when) - the full reference for `fresh_when`, strong vs weak ETags, and when conditional GETs pay off.
- [Static Assets](/docs/assets) - how fingerprinted asset URLs let the browser cache CSS and JS aggressively without ever showing a stale version.
- [Background Tasks](/docs/tasks) - schedule `cache.delete_expired()` to keep the SQLite cache table small.
- [Models](/docs/models) - the `updated_at` column that drives so much of this guide is a property of `BaseModel`; the models guide covers how it's maintained and when to override it.
- [Jx Components and Layouts](/docs/jx_components) - the templates that `{% cache %}` wraps. Component-level CSS/JS dependencies are also cached aggressively.
