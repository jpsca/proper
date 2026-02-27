title: Cache
----

# Cache

Proper provides a server-side key-value cache backed by SQLite. It's used for fragment caching in templates, rate limiting, and storing any data that's expensive to compute. The cache is available as `app.cache` from anywhere in the application.


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

### 2.2 Increment

The `increment` method atomically increments a counter. If the key doesn't exist or has expired, it starts from the given value:

```python
# Increment by 1 (default)
count = cache.increment("page:views:42")

# Increment by a custom amount
count = cache.increment("api:bytes:user-7", 1024)

# With a custom TTL
count = cache.increment("page:views:42", expires_in=3600)
```

This is used internally by the rate limiting system.

### 2.3 Batch Operations

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

### 2.4 Cleanup

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

### 3.1 Caching Model Objects

Pass a model object or collection instead of a string key. The cache key is derived from the object's class name and ID:

```html+jinja
{% cache card %}
  <div class="card">
    <h2>{{ card.title }}</h2>
    <p>{{ card.body }}</p>
  </div>
{% endcache %}
```

For collections:

```html+jinja
{% cache cards %}
  {% for card in cards %}
    <div class="card">{{ card.title }}</div>
  {% endfor %}
{% endcache %}
```

### 3.2 Expiration and Versioning

Set a TTL with `expires_in` (in seconds) or a manual version:

```html+jinja
{% cache "sidebar", expires_in=3600 %}
  ... refreshed every hour ...
{% endcache %}

{% cache card, version="v2" %}
  ... invalidated when version changes ...
{% endcache %}
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
key_for("view", card)               # "view:0/card/42"
key_for("view", cards)              # "view:0/card/col/5"
```

- **String**: returned as-is, lowercased
- **Object**: delegates to `key_for_object`
- **List/tuple**: delegates to `key_for_collection`
- **Dict, bytes, bytearray**: raises `ValueError`

### 5.2 key_for_object

Generates a key from a model object:

```python
key_for_object("view", card)        # "view:0/card/42"
```

The key format is `"{prefix}:{version}/{class_name}/{id}"`, all lowercased.

### 5.3 key_for_collection

Generates a key from a collection of objects:

```python
key_for_collection("view", cards)   # "view:0/card/col/5"
```

The key format is `"{prefix}:{version}/{class_name}/col/{count}"`, all lowercased.


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

    def delete(self, key):
        self.client.delete(key)
```

Register it in your config:

```python
CACHE = {
    "type": "myapp.cache.MemcachedCache",
    "servers": ["127.0.0.1:11211"],
}
```

All keys in the config dict (except `type`) are passed as keyword arguments to the constructor.
