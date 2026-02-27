title: Caching
----

# Caching

Proper provides a server-side key-value cache backed by SQLite or Redis. It's used for fragment caching in templates, rate limiting, and storing any data that's expensive to compute. The cache is available as `app.cache` from anywhere in the application.


## 1. Configuration

Cache settings live in `config/storage.py` under the `CACHE` key. The generated app includes per-environment defaults:

```python {title="myapp/config/storage.py"}
# Development — in-memory, fast, cleared on restart
CACHE = {
    "type": "proper.cache.SqliteCache",
    "database": ":memory:",
}

# Testing — disabled
if env == "test":
    CACHE = {
        "type": "proper.cache.NoCache",
    }

# Production — persisted to disk
if env == "prod":
    CACHE = {
        "type": "proper.cache.SqliteCache",
        "database": "storage/cache.sqlite3",
    }
```

### 1.1 SqliteCache Options

| Option       | Default               | Description                                      |
|--------------|-----------------------|--------------------------------------------------|
| `database`   | (required)            | Path to the SQLite file, or `":memory:"`         |
| `expires_in` | `172800` (2 days)     | Default TTL in seconds for cached values         |
| `serializer` | `None`                | Custom serializer (uses pickle by default)       |
| `timeout`    | `5`                   | SQLite connection timeout in seconds             |

Any additional keys are passed as SQLite pragmas. The cache always enables WAL mode for concurrent reads and writes.

### 1.2 Backends

| Backend      | Import path                | Description                                 |
|--------------|----------------------------|---------------------------------------------|
| `SqliteCache`| `proper.cache.SqliteCache` | SQLite-backed cache with TTL expiration     |
| `RedisCache` | `proper.cache.RedisCache`  | Redis-backed cache (requires `redis` package) |
| `NoCache`    | `proper.cache.NoCache`     | Null object — all operations are no-ops     |

`NoCache` is useful for testing, where you want deterministic behavior without cached state.

There is no separate in-memory backend. Use `SqliteCache` with `":memory:"` as the database — it behaves like a memory cache (fast, no disk I/O) and is cleared when the process restarts. This is the default in development.

### 1.3 RedisCache

Redis is an optional dependency. The `redis` package is only required if you use `RedisCache` — it won't be imported otherwise. Install it with:

```bash
pip install redis
```

Configuration:

```python {title="myapp/config/storage.py"}
CACHE = {
    "type": "proper.cache.RedisCache",
    "url": "redis://localhost:6379/0",
}
```

Options:

| Option       | Default                       | Description                                      |
|--------------|-------------------------------|--------------------------------------------------|
| `url`        | `"redis://localhost:6379/0"`  | Redis connection URL                             |
| `expires_in` | `172800` (2 days)             | Default TTL in seconds for cached values         |
| `serializer` | `None`                        | Custom serializer (uses pickle by default)       |

Any additional keys are passed to `redis.from_url()` (e.g., `decode_responses`, `socket_timeout`).

Redis handles expiration natively via TTL, so `delete_expired()` is a no-op — there is no need to schedule cleanup.


## 2. Using the Cache Store

Access the cache from a controller via `self.app.cache`, or from anywhere via `current.app.cache`:

```python
from proper import current

cache = current.app.cache

# Store a value (uses the default TTL)
cache.set("stats:daily", computed_stats)

# Store with a custom TTL
cache.set("stats:daily", computed_stats, expires_in=3600)

# Retrieve a value (returns None if missing or expired)
stats = cache.get("stats:daily")

# Delete a value
cache.delete("stats:daily")
```

### 2.1 Expiration

The TTL is set at write time. Every call to `set` computes an `expires_at` timestamp from the current time plus `expires_in`. If `expires_in` is not provided, the instance default is used (2 days by default).

On `get`, the cache checks if the stored `expires_at` has passed. If the value has expired, it is deleted and `None` is returned.

### 2.2 Get or Set

`get_or_set` fetches a value from the cache. On a miss, it computes and stores a default. The default can be a plain value or a callable:

```python
# With a plain value
stats = cache.get_or_set("stats:daily", compute_stats())

# With a callable — only invoked on a cache miss
stats = cache.get_or_set("stats:daily", lambda: compute_stats(), expires_in=3600)
```

#### Preventing Thundering Herd with `race_condition_ttl`

When a popular cache key expires and many requests arrive simultaneously, they all see a miss and all recompute the same expensive value. This is called the thundering herd problem.

`race_condition_ttl` prevents this. When the first caller finds an expired key within the race window, it extends the stale entry's TTL so that other callers continue serving the old value while the first caller recomputes:

```python
stats = cache.get_or_set(
    "stats:daily",
    lambda: Stats.compute(),
    expires_in=300,            # logical expiry: 5 minutes
    race_condition_ttl=10,     # serve stale data for up to 10s while recomputing
)
```

The sequence:

1. Key expires
2. Request A sees the miss, **extends the stale entry by 10 seconds**, starts recomputing
3. Requests B through N arrive, find the extended (stale) entry, return it immediately
4. Request A finishes, stores the fresh value
5. All subsequent requests get the new value

Without `race_condition_ttl`, all N requests would compute simultaneously.

### 2.3 Increment and Decrement

The `increment` and `decrement` methods atomically modify a counter. If the key doesn't exist or has expired, it starts from the given value:

```python
# Increment by 1 (default)
count = cache.increment("page:views:42")

# Increment by a custom amount
count = cache.increment("api:bytes:user-7", 1024)

# With a custom TTL
count = cache.increment("page:views:42", expires_in=3600)

# Decrement
count = cache.decrement("quota:remaining:user-7")
count = cache.decrement("quota:remaining:user-7", 5)
```

`increment` is used internally by the rate limiting system.

### 2.4 Batch Operations

Use `read_multi` and `write_multi` to operate on multiple keys at once. With the Redis backend, these map to `MGET` and pipelined `SET` commands — a single round-trip instead of N:

```python
# Read multiple keys at once — returns a dict of hits (misses are absent)
results = cache.read_multi("user:1", "user:2", "user:3")
# => {"user:1": ..., "user:3": ...}

# Write multiple keys at once
cache.write_multi({
    "user:1": user1_data,
    "user:2": user2_data,
    "user:3": user3_data,
}, expires_in=3600)
```

With the SQLite backend, `read_multi` uses a single `WHERE key IN (...)` query and `write_multi` runs inside a single transaction.

### 2.5 Clear

Remove all entries from the cache:

```python
cache.clear()
```

With SQLite, this deletes all rows from the cache table. With Redis, it calls `FLUSHDB`.

### 2.6 Cleanup

Expired entries are deleted lazily on read (when a `get` or `increment` finds an expired key). To bulk-delete all expired entries, call `delete_expired`:

```python
cache.delete_expired()
```

Since each entry stores its own `expires_at`, no TTL parameter is needed. This can be called from a background task on a schedule.


## 3. Fragment Caching

Fragment caching stores rendered HTML blocks so expensive template rendering is skipped on subsequent requests. Use the `{% cache %}` tag in Jinja templates:

```html+jinja
{% cache "sidebar" %}
  ... expensive rendering ...
{% endcache %}
```

On the first render, the block is rendered and stored in the cache under the key `"sidebar"`. On subsequent requests, the cached HTML is returned directly without re-rendering.

The full syntax is:

```html+jinja
{% cache key [, expires_in=seconds] [, version=string] [, race_condition_ttl=seconds] %}
  ...
{% endcache %}
```

| Argument             | Type             | Description                                                                                               |
|----------------------|------------------|-----------------------------------------------------------------------------------------------------------|
| `key`                | string, object, or collection | **Required.** A string cache key, a model object, or a collection of model objects. See [section 3.1](#31-cache-key). |
| `expires_in`         | int              | TTL in seconds. If omitted, uses the cache backend's default (2 days).                                    |
| `version`            | string or int    | Manual version tag appended to the key. When changed, the old entry is effectively invalidated.           |
| `race_condition_ttl` | int              | Seconds to extend a stale entry while one request re-renders. Prevents the thundering herd problem.       |

### 3.1 Cache Key

The first argument to `{% cache %}` determines how the cache key is generated:

**String** — used as-is (lowercased). Good for fragments that aren't tied to a specific record:

```html+jinja
{% cache "sidebar" %}
  ...
{% endcache %}
```

**Model object** — the key is derived from the object's class name, ID, and `updated_at` timestamp. When the record is updated, `updated_at` changes, which changes the key and automatically invalidates the cached fragment:

```html+jinja
{% cache card %}
  <div class="card">
    <h2>{{ card.title }}</h2>
    <p>{{ card.body }}</p>
  </div>
{% endcache %}
```

**Collection** — the key is derived from the class name, the count of objects, and the maximum `updated_at` across the collection. The fragment invalidates when any object is added, removed, or updated:

```html+jinja
{% cache cards %}
  {% for card in cards %}
    <div class="card">{{ card.title }}</div>
  {% endfor %}
{% endcache %}
```

### 3.2 Expiration and Versioning

Set a TTL with `expires_in` (in seconds). The fragment will be re-rendered after the TTL expires, regardless of whether the underlying data changed:

```html+jinja
{% cache "sidebar", expires_in=3600 %}
  ... refreshed every hour ...
{% endcache %}
```

Use `version` to manually invalidate a fragment. This is useful when the template markup changes but the data hasn't — bumping the version forces a re-render:

```html+jinja
{% cache card, version="v2" %}
  ... invalidated when version changes ...
{% endcache %}
```

When caching model objects, `version` is normally unnecessary because `updated_at` handles invalidation automatically. Use it when you change the template itself and need to bust stale HTML.

### 3.3 Preventing Thundering Herd

For heavily-trafficked fragments, use `race_condition_ttl` to prevent many requests from re-rendering the same block simultaneously when the cache expires:

```html+jinja
{% cache "sidebar", expires_in=300, race_condition_ttl=10 %}
  ... expensive rendering ...
{% endcache %}
```

When the first request finds the fragment expired, it extends the stale entry by 10 seconds and re-renders. Other requests arriving during that window continue serving the stale HTML until the fresh version is stored. See [section 2.2](#22-get-or-set) for details on how this works.

### 3.4 Russian Doll Caching

Russian doll caching nests cached fragments inside other cached fragments. When an inner record changes, only it and its ancestors need re-rendering — sibling fragments remain cached.

The template side uses nested `{% cache %}` blocks:

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

The challenge: when a comment changes, its own fragment invalidates (its `updated_at` changed), but the outer `{% cache post %}` fragment still has the old `post.updated_at` and keeps serving stale HTML.

The fix is to declare `touches` on the child model. Use the `RussianDollCached` mixin (found in `models/concerns/russian_doll_cached.py`):

```python {title="models/comment.py"}
class Comment(RussianDollCached, BaseModel):
    post = pw.ForeignKeyField(Post, backref="comments")
    body = pw.TextField()

    touches = ("post",)
```

Now when a comment is saved or deleted, it automatically bumps its post's `updated_at`, which invalidates the outer fragment. The post fragment re-renders, but since only one comment changed, all the other `{% cache comment %}` fragments are still cached and served from the store.

Touches cascade through multiple levels. If replies touch comments and comments touch posts, saving a reply invalidates all three layers:

```python {title="models/reply.py"}
class Reply(RussianDollCached, BaseModel):
    comment = pw.ForeignKeyField(Comment, backref="replies")
    body = pw.TextField()

    touches = ("comment",)
```

You can also bump a record's `updated_at` manually with `touch()`:

```python
post.touch()
```


## 4. HTTP Caching

Separate from the server-side cache store, Proper supports HTTP conditional requests using ETag and Last-Modified headers. This is handled at the response level.

### 4.1 fresh_when

Use `self.response.fresh_when()` to set caching headers on a response. Pass model objects with an `updated_at` attribute:

```python
def show(self):
    self.card = Card.get_by_id(self.params["card_id"])
    self.response.fresh_when(self.card)

def index(self):
    self.cards = Card.select().order_by(Card.created_at.desc())
    self.response.fresh_when(self.cards)
```

If the client already has the latest version (matching ETag or Last-Modified), Proper returns `304 Not Modified` with an empty body instead of re-rendering the page.

Options:

```python
self.response.fresh_when(
    self.card,
    strong=True,     # Strong ETag (default: weak)
    public=True,     # Allow proxy caches (default: private)
)
```

You can also set the ETag and Last-Modified explicitly:

```python
self.response.fresh_when(etag="v1-abc123", last_modified=some_datetime)
```

### 4.2 Cache-Control

Set the `Cache-Control` header directly for custom caching strategies:

```python
self.response.set_cache_control("max-age=3600", "public")
self.response.set_cache_control("max-age=0", "private", "must-revalidate")
self.response.set_cache_control("max-age=31536000", "public", "immutable")
```

### 4.3 Static Assets

Static files are cached automatically. Fingerprinted assets (URLs containing a hash) are served with `Cache-Control: public, max-age=31536000, immutable` (1 year). Non-fingerprinted assets use `Cache-Control: public, max-age=0, must-revalidate` and support conditional requests via ETag and If-Modified-Since.


## 5. Cache Keys

The `proper.cache` module provides helper functions for generating cache keys from objects:

```python
from proper.cache import key_for, key_for_object, key_for_collection
```

### 5.1 key_for

A dispatcher that generates a cache key based on the type of input:

```python
key_for("view", "sidebar")          # "sidebar"
key_for("view", card)               # "view:1735689600.0/card/42"
key_for("view", cards)              # "view:1735689600.0/card/col/5"
```

- **String**: returned as-is, lowercased. The `prefix` and `version` parameters are ignored.
- **Object**: delegates to `key_for_object`
- **List/tuple**: delegates to `key_for_collection`
- **Dict, bytes, bytearray**: raises `ValueError`

### 5.2 key_for_object

Generates a key from a model object:

```python
key_for_object("view", card)        # "view:1735689600.0/card/42"
```

The key format is `"{prefix}:{version}/{class_name}/{id}"`, all lowercased. If no explicit `version` is given, the object's `updated_at` timestamp is used automatically. This is the mechanism that makes fragment and Russian doll caching work — when a record is updated, its `updated_at` changes, which changes the cache key, effectively invalidating the old entry.

### 5.3 key_for_collection

Generates a key from a collection of objects:

```python
key_for_collection("view", cards)   # "view:1735689600.0/card/col/5"
```

The key format is `"{prefix}:{version}/{class_name}/col/{count}"`, all lowercased. If no explicit `version` is given, the maximum `updated_at` across all objects in the collection is used. This means the cache key changes whenever any object in the collection is updated.


## 6. Custom Cache Backends

To implement a custom backend, subclass `BaseCache` and implement its methods:

```python
from proper.cache import BaseCache
import memcache


class MemcachedCache(BaseCache):
    def __init__(self, servers, *, expires_in=172800, serializer=None):
        super().__init__(serializer=serializer)
        self.expires_in = expires_in
        self.client = memcache.Client(servers)

    def set(self, key, value, *, expires_in=None):
        ttl = expires_in if expires_in is not None else self.expires_in
        data = self.serialize(value)
        self.client.set(key, data, time=ttl)

    def get(self, key):
        data = self.client.get(key)
        if data is None:
            return None
        return self.deserialize(data)

    def increment(self, key, value=1, *, expires_in=None):
        result = self.client.incr(key, value)
        if result is None:
            self.set(key, value, expires_in=expires_in)
            return value
        return result

    def decrement(self, key, value=1, *, expires_in=None):
        result = self.client.decr(key, value)
        if result is None:
            self.set(key, -value, expires_in=expires_in)
            return -value
        return result

    def delete(self, key):
        self.client.delete(key)

    def clear(self):
        self.client.flush_all()
```

Register it in your config:

```python
CACHE = {
    "type": "myapp.cache.MemcachedCache",
    "servers": ["127.0.0.1:11211"],
}
```

All keys in the config dict (except `type`) are passed as keyword arguments to the constructor.
