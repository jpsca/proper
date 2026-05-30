import threading
from datetime import datetime
from time import time
from unittest.mock import MagicMock

import pytest

from proper.cache import (
    BaseCache,
    FragmentCacheExtension,
    NoCache,
    SqliteCache,
    key_for,
    key_for_collection,
    key_for_object,
)
from proper.cache.base import NoSerializer, Serializer, SerializerProtocol


class TestSerializerProtocol:
    def test_serialize_raises(self):
        with pytest.raises(NotImplementedError):
            SerializerProtocol.serialize(None, b"")

    def test_deserialize_raises(self):
        with pytest.raises(NotImplementedError):
            SerializerProtocol.deserialize(None, b"")


class TestNoSerializer:
    def test_serialize_raises(self):
        s = NoSerializer()
        with pytest.raises(NotImplementedError):
            s.serialize("hello")

    def test_deserialize_raises(self):
        s = NoSerializer()
        with pytest.raises(NotImplementedError):
            s.deserialize(b"hello")


class TestSerializer:
    def test_roundtrip_string(self):
        s = Serializer()
        data = s.serialize("hello")
        assert s.deserialize(data) == "hello"

    def test_roundtrip_dict(self):
        s = Serializer()
        obj = {"a": 1, "b": [2, 3]}
        data = s.serialize(obj)
        assert s.deserialize(data) == obj

    def test_roundtrip_none(self):
        s = Serializer()
        data = s.serialize(None)
        assert s.deserialize(data) is None

    def test_custom_protocol(self):
        s = Serializer(protocol=2)
        assert s.protocol == 2
        data = s.serialize(42)
        assert s.deserialize(data) == 42

    def test_none_protocol_uses_highest(self):
        import pickle
        s = Serializer(protocol=None)
        assert s.protocol == pickle.HIGHEST_PROTOCOL


class TestBaseCache:
    def test_default_serializer(self):
        cache = BaseCache()
        assert isinstance(cache.serializer, Serializer)

    def test_custom_serializer(self):
        custom = MagicMock()
        cache = BaseCache(serializer=custom)
        assert cache.serializer is custom

    def test_set_raises(self):
        cache = BaseCache()
        with pytest.raises(NotImplementedError):
            cache.set("key", "value")

    def test_get_raises(self):
        cache = BaseCache()
        with pytest.raises(NotImplementedError):
            cache.get("key")

    def test_increment_raises(self):
        cache = BaseCache()
        with pytest.raises(NotImplementedError):
            cache.increment("key")

    def test_delete_raises(self):
        cache = BaseCache()
        with pytest.raises(NotImplementedError):
            cache.delete("key")

    def test_update_is_set(self):
        assert BaseCache.update is BaseCache.set

    def test_delete_expired_is_noop(self):
        cache = BaseCache()
        cache.delete_expired()  # should not raise

    def test_serialize_delegates(self):
        cache = BaseCache()
        data = cache.serialize("hello")
        assert cache.deserialize(data) == "hello"


class TestNoCache:
    def test_get_returns_none(self):
        cache = NoCache()
        assert cache.get("key") is None

    def test_set_is_noop(self):
        cache = NoCache()
        cache.set("key", "value")  # should not raise

    def test_increment_returns_zero(self):
        cache = NoCache()
        assert cache.increment("key") == 0

    def test_delete_is_noop(self):
        cache = NoCache()
        cache.delete("key")  # should not raise

    def test_serializer_is_no_serializer(self):
        cache = NoCache()
        assert isinstance(cache.serializer, NoSerializer)

    def test_read_multi_returns_empty(self):
        cache = NoCache()
        assert cache.read_multi("a", "b") == {}

    def test_write_multi_is_noop(self):
        cache = NoCache()
        cache.write_multi({"a": 1, "b": 2})  # should not raise


@pytest.fixture
def cache():
    c = SqliteCache(":memory:")
    yield c
    c.close()


class TestSqliteCache:
    def test_memory_based(self, cache):
        assert cache.memory_based is True

    def test_set_and_get(self, cache):
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self, cache):
        assert cache.get("nonexistent") is None

    def test_set_overwrites(self, cache):
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_set_complex_value(self, cache):
        obj = {"list": [1, 2, 3], "nested": {"a": True}}
        cache.set("complex", obj)
        assert cache.get("complex") == obj

    def test_set_with_custom_expires_in(self, cache):
        cache.set("key1", "value1", expires_in=3600)
        assert cache.get("key1") == "value1"

    def test_set_with_short_expires_in(self, cache):
        cache.set("key1", "value1", expires_in=1)
        # Simulate expiration by setting expires_at to the past
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "key1").execute()
        assert cache.get("key1") is None

    def test_get_expired_key(self, cache):
        cache.set("key1", "value1", expires_in=1)
        # Simulate expiration by updating expires_at directly
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "key1").execute()
        assert cache.get("key1") is None

    def test_get_not_expired(self, cache):
        cache.set("key1", "value1", expires_in=3600)
        assert cache.get("key1") == "value1"

    def test_get_expired_deletes_key(self, cache):
        cache.set("key1", "value1", expires_in=1)
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "key1").execute()
        cache.get("key1")
        # Key should be deleted
        assert cache._count() == 0

    def test_get_or_set_miss(self, cache):
        result = cache.get_or_set("key", "default_value")
        assert result == "default_value"
        assert cache.get("key") == "default_value"

    def test_get_or_set_hit(self, cache):
        cache.set("key", "existing")
        result = cache.get_or_set("key", "default_value")
        assert result == "existing"

    def test_get_or_set_callable(self, cache):
        called = []
        def compute():
            called.append(1)
            return "computed"

        result = cache.get_or_set("key", compute)
        assert result == "computed"
        assert cache.get("key") == "computed"
        assert len(called) == 1

    def test_get_or_set_callable_not_called_on_hit(self, cache):
        cache.set("key", "existing")
        called = []
        result = cache.get_or_set("key", lambda: called.append(1) or "new")
        assert result == "existing"
        assert len(called) == 0

    def test_get_or_set_with_expires_in(self, cache):
        cache.get_or_set("key", "value", expires_in=1)
        assert cache.get("key") == "value"
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "key").execute()
        assert cache.get("key") is None

    def test_get_or_set_race_condition_ttl_serves_stale(self, cache):
        """Within the race window, other callers get the stale value."""
        cache.set("key", "original", expires_in=100)
        from proper.cache.sqlite_cache import Cache
        # Expire the key 2 seconds ago
        Cache.update(expires_at=int(time()) - 2).where(Cache.key == "key").execute()

        # First caller recomputes
        result = cache.get_or_set("key", lambda: "recomputed", expires_in=100, race_condition_ttl=10)
        assert result == "recomputed"

        # Simulate a second concurrent caller seeing the extended stale entry.
        # After the first caller bumped the TTL and then wrote the new value,
        # subsequent callers get the fresh value.
        result2 = cache.get_or_set("key", lambda: "should_not_run", expires_in=100, race_condition_ttl=10)
        assert result2 == "recomputed"

    def test_get_or_set_race_condition_ttl_extends_stale(self, cache):
        """The stale entry's TTL is extended so others don't also recompute."""
        cache.set("key", "original", expires_in=100)
        from proper.cache.sqlite_cache import Cache
        # Expire the key 2 seconds ago
        Cache.update(expires_at=int(time()) - 2).where(Cache.key == "key").execute()

        # Simulate what happens between the TTL bump and the recompute:
        # read the row, check it's in the race window, bump it
        row_before = Cache.get_or_none(Cache.key == "key")
        old_expires = row_before.expires_at

        cache.get_or_set("key", lambda: "new", expires_in=100, race_condition_ttl=10)

        # The key now has a fresh expires_at from the set() call
        row_after = Cache.get_or_none(Cache.key == "key")
        assert row_after.expires_at > old_expires

    def test_get_or_set_race_condition_ttl_expired_beyond_window(self, cache):
        """Beyond the race window, treat as a normal miss."""
        cache.set("key", "original", expires_in=100)
        from proper.cache.sqlite_cache import Cache
        # Expire the key 20 seconds ago, beyond the 10s window
        Cache.update(expires_at=int(time()) - 20).where(Cache.key == "key").execute()

        result = cache.get_or_set("key", lambda: "fresh", expires_in=100, race_condition_ttl=10)
        assert result == "fresh"

    def test_get_or_set_race_condition_ttl_not_expired(self, cache):
        """If the key is still valid, return it without recomputing."""
        cache.set("key", "valid", expires_in=3600)
        called = []
        result = cache.get_or_set("key", lambda: called.append(1) or "new", race_condition_ttl=10)
        assert result == "valid"
        assert len(called) == 0

    def test_increment_new_key(self, cache):
        result = cache.increment("counter")
        assert result == 1

    def test_increment_existing_key(self, cache):
        cache.increment("counter")
        result = cache.increment("counter")
        assert result == 2

    def test_increment_custom_value(self, cache):
        cache.increment("counter", 5)
        result = cache.increment("counter", 3)
        assert result == 8

    def test_increment_expired_key_resets(self, cache):
        cache.increment("counter", 10, expires_in=1)
        # Simulate expiration
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "counter").execute()
        result = cache.increment("counter", 1, expires_in=1)
        assert result == 1

    def test_increment_not_expired(self, cache):
        cache.increment("counter", 5, expires_in=3600)
        result = cache.increment("counter", 3, expires_in=3600)
        assert result == 8

    def test_increment_default_expires_in(self, cache):
        cache.increment("counter", 5)
        result = cache.increment("counter", 3)
        assert result == 8

    def test_decrement(self, cache):
        cache.increment("counter", 10)
        result = cache.decrement("counter")
        assert result == 9
        result = cache.decrement("counter", 4)
        assert result == 5

    def test_delete(self, cache):
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        cache.delete("nonexistent")  # should not raise

    def test_clear(self, cache):
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache._count() == 0

    def test_delete_expired(self, cache):
        cache.set("old", "value", expires_in=1)
        cache.set("new", "value")
        # Simulate expiration of "old"
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "old").execute()
        cache.delete_expired()
        assert cache.get("old") is None
        assert cache.get("new") == "value"

    def test_delete_expired_default(self, cache):
        cache.set("old", "value", expires_in=1)
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "old").execute()
        cache.delete_expired()
        assert cache._count() == 0

    def test_count(self, cache):
        assert cache._count() == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache._count() == 2

    def test_close(self):
        c = SqliteCache(":memory:")
        c.close()
        # After close, connection should not be usable
        assert not c.database.is_connection_usable()

    def test_check_conn_reconnects(self, cache):
        cache.database.close()
        assert not cache.database.is_connection_usable()
        cache.check_conn()
        assert cache.database.is_connection_usable()

    def test_check_conn_already_connected(self, cache):
        assert cache.database.is_connection_usable()
        cache.check_conn()  # should not raise
        assert cache.database.is_connection_usable()

    def test_memory_cache_shared_across_threads(self, cache):
        cache.set("key", "from_main")
        results = []

        def worker():
            results.append(cache.get("key"))
            cache.set("worker_key", "from_worker")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert results[0] == "from_main"
        assert cache.get("worker_key") == "from_worker"

    def test_file_based_cache(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        c = SqliteCache(db_path)
        c.create_tables()
        c.set("key", "value")
        assert c.get("key") == "value"
        assert c.memory_based is False
        c.close()

    def test_custom_expires_in(self):
        c = SqliteCache(":memory:", expires_in=10)
        assert c.expires_in == 10
        c.close()

    def test_wal_mode_set(self, tmp_path):
        c = SqliteCache(str(tmp_path / "wal.db"))
        c.create_tables()
        result = c.database.execute_sql("PRAGMA journal_mode").fetchone()
        assert result[0] == "wal"
        c.close()

    def test_read_multi_all_hits(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        result = cache.read_multi("a", "b", "c")
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_read_multi_partial_hits(self, cache):
        cache.set("a", 1)
        cache.set("c", 3)
        result = cache.read_multi("a", "b", "c")
        assert result == {"a": 1, "c": 3}

    def test_read_multi_all_misses(self, cache):
        result = cache.read_multi("x", "y", "z")
        assert result == {}

    def test_read_multi_skips_expired(self, cache):
        cache.set("fresh", "yes")
        cache.set("stale", "no", expires_in=1)
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=0).where(Cache.key == "stale").execute()
        result = cache.read_multi("fresh", "stale")
        assert result == {"fresh": "yes"}
        # Expired key should be deleted
        assert cache._count() == 1

    def test_read_multi_no_keys(self, cache):
        result = cache.read_multi()
        assert result == {}

    def test_write_multi(self, cache):
        cache.write_multi({"a": 1, "b": 2, "c": 3})
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_write_multi_custom_ttl(self, cache):
        cache.write_multi({"a": 1, "b": 2}, expires_in=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_write_multi_empty(self, cache):
        cache.write_multi({})
        assert cache._count() == 0


class TestKeyForObject:
    def test_basic(self):
        obj = MagicMock()
        obj.__class__.__name__ = "Card"
        obj.id = 42
        obj.updated_at = None
        key = key_for_object("cache", obj)
        assert key == "cache:0/card/42"

    def test_with_updated_at(self):
        obj = MagicMock()
        obj.__class__.__name__ = "Card"
        obj.id = 42
        obj.updated_at = datetime(2024, 1, 15, 12, 0, 0)
        ts = str(datetime.timestamp(obj.updated_at))
        key = key_for_object("cache", obj)
        assert key == f"cache:{ts}/card/42"

    def test_with_explicit_version(self):
        obj = MagicMock()
        obj.__class__.__name__ = "Card"
        obj.id = 42
        obj.updated_at = None
        key = key_for_object("cache", obj, version="v2")
        assert key == "cache:v2/card/42"

    def test_no_id_attr(self):
        obj = MagicMock(spec=[])
        obj.__class__ = type("Thing", (), {})
        key = key_for_object("prefix", obj)
        assert "?" in key

    def test_lowercase(self):
        obj = MagicMock()
        obj.__class__.__name__ = "MyModel"
        obj.id = 1
        obj.updated_at = None
        key = key_for_object("PREFIX", obj)
        assert key == "prefix:0/mymodel/1"


class TestKeyForCollection:
    def test_basic(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = None
        obj2 = MagicMock(spec=["updated_at"])
        obj2.__class__.__name__ = "Card"
        obj2.updated_at = None
        key = key_for_collection("cache", [obj1, obj2])
        assert key == "cache:0/card/col/2"

    def test_with_updated_at(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = datetime(2024, 1, 15, 12, 0, 0)
        obj2 = MagicMock(spec=["updated_at"])
        obj2.__class__.__name__ = "Card"
        obj2.updated_at = datetime(2024, 6, 1, 12, 0, 0)
        ts = str(datetime.timestamp(obj2.updated_at))
        key = key_for_collection("cache", [obj1, obj2])
        assert key == f"cache:{ts}/card/col/2"

    def test_with_explicit_version(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = None
        key = key_for_collection("cache", [obj1], version="v3")
        assert key == "cache:v3/card/col/1"

    def test_no_updated_at(self):
        obj1 = MagicMock(spec=[])
        obj1.__class__.__name__ = "Item"
        key = key_for_collection("cache", [obj1])
        assert key == "cache:0/item/col/1"


class TestKeyFor:
    def test_string_key(self):
        assert key_for("prefix", "MY-KEY") == "my-key"

    def test_string_key_ignores_prefix(self):
        assert key_for("anything", "Hello World") == "hello world"

    def test_object_key(self):
        obj = MagicMock(spec=["id", "updated_at"])
        obj.__class__ = type("Card", (), {})
        obj.id = 1
        obj.updated_at = None
        key = key_for("cache", obj)
        assert key == "cache:0/card/1"

    def test_collection_key(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = None
        key = key_for("cache", [obj1])
        assert key == "cache:0/card/col/1"

    def test_tuple_collection(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = None
        key = key_for("cache", (obj1,))
        assert key == "cache:0/card/col/1"

    def test_dict_raises(self):
        with pytest.raises(ValueError, match="key must be"):
            key_for("prefix", {"a": 1})

    def test_bytes_raises(self):
        with pytest.raises(ValueError, match="key must be"):
            key_for("prefix", b"hello")

    def test_bytearray_raises(self):
        with pytest.raises(ValueError, match="key must be"):
            key_for("prefix", bytearray(b"hello"))


class TestFragmentCacheExtension:
    def _make_ext(self, cache=None):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = cache or SqliteCache(":memory:")
        return ext

    def test_cache_miss_renders_and_stores(self):
        ext = self._make_ext()
        result = ext._cache_support("my-key", caller=lambda: "rendered", name="view")
        assert result == "rendered"
        assert ext.environment.app_cache.get("my-key") == "rendered"

    def test_cache_hit_returns_cached(self):
        ext = self._make_ext()
        ext.environment.app_cache.set("my-key", "cached-value")
        result = ext._cache_support("my-key", caller=lambda: "fresh", name="view")
        assert result == "cached-value"

    def test_cache_with_expires_in(self):
        ext = self._make_ext()
        ext._cache_support("my-key", caller=lambda: "value", name="view", expires_in=300)
        assert ext.environment.app_cache.get("my-key") == "value"

    def test_cache_with_version(self):
        ext = self._make_ext()
        ext._cache_support("my-key", caller=lambda: "value", name="", version="v2")
        # key_for with version="v2" produces "my-key" for string keys
        assert ext.environment.app_cache.get("my-key") == "value"

    def test_default_name_prefix(self):
        ext = self._make_ext()
        ext._cache_support("my-key", caller=lambda: "value", name="")
        assert ext.environment.app_cache.get("my-key") == "value"

    def test_race_condition_ttl(self):
        cache = SqliteCache(":memory:")
        ext = self._make_ext(cache)
        cache.set("my-key", "stale", expires_in=100)
        # Expire the key 2 seconds ago
        from proper.cache.sqlite_cache import Cache
        Cache.update(expires_at=int(time()) - 2).where(Cache.key == "my-key").execute()

        result = ext._cache_support(
            "my-key", caller=lambda: "fresh", name="view",
            expires_in=300, race_condition_ttl=10,
        )
        assert result == "fresh"
        assert cache.get("my-key") == "fresh"

    def test_tags(self):
        assert "cache" in FragmentCacheExtension.tags

    def test_parse_and_render(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        env.app_cache = SqliteCache(":memory:")

        template = env.from_string(
            "{% cache('my-key') %}expensive{% endcache %}"
        )
        result = template.render()
        assert result == "expensive"
        assert env.app_cache.get("my-key") == "expensive"

    def test_parse_cache_hit(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        env.app_cache = SqliteCache(":memory:")
        env.app_cache.set("key", "cached")

        template = env.from_string(
            "{% cache('key') %}fresh{% endcache %}"
        )
        result = template.render()
        assert result == "cached"

    def test_parse_with_expires_in(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        env.app_cache = SqliteCache(":memory:")

        template = env.from_string(
            "{% cache('key', expires_in=300) %}body{% endcache %}"
        )
        result = template.render()
        assert result == "body"
        assert env.app_cache.get("key") == "body"
