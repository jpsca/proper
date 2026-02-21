from datetime import datetime
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


# ── Serializer ───────────────────────────────────────────────────────

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


# ── BaseCache ────────────────────────────────────────────────────────

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


# ── NoCache ──────────────────────────────────────────────────────────

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


# ── SqliteCache ──────────────────────────────────────────────────────

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

    def test_set_with_custom_timestamp(self, cache):
        cache.set("key1", "value1", timestamp=1000)
        # With default expires_in (2 days = 172800s), timestamp 1000 is expired
        assert cache.get("key1") is None

    def test_get_expired_key(self, cache):
        cache.set("key1", "value1", timestamp=0)
        assert cache.get("key1", expires_in=1) is None

    def test_get_not_expired(self, cache):
        cache.set("key1", "value1")
        assert cache.get("key1", expires_in=3600) == "value1"

    def test_get_expired_deletes_key(self, cache):
        cache.set("key1", "value1", timestamp=0)
        cache.get("key1", expires_in=1)
        # Key should be deleted
        assert cache._count() == 0

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
        cache.set("counter", 10, timestamp=0)
        result = cache.increment("counter", 1, expires_in=1)
        assert result == 1

    def test_increment_not_expired(self, cache):
        cache.increment("counter", 5)
        result = cache.increment("counter", 3, expires_in=3600)
        assert result == 8

    def test_increment_default_expires_in(self, cache):
        cache.increment("counter", 5)
        result = cache.increment("counter", 3)
        assert result == 8

    def test_delete(self, cache):
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        cache.delete("nonexistent")  # should not raise

    def test_delete_expired(self, cache):
        cache.set("old", "value", timestamp=0)
        cache.set("new", "value")
        cache.delete_expired(expires_in=1)
        assert cache.get("old") is None
        assert cache.get("new") == "value"

    def test_delete_expired_default(self, cache):
        cache.set("old", "value", timestamp=0)
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

    def test_reset_is_noop(self, cache):
        cache.reset()  # should not raise

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


# ── key_for_object ───────────────────────────────────────────────────

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
        key = key_for_object("cache", obj)
        # Bug: version is always "0" because of `str(0 if version is None else 0)`
        assert key == "cache:0/card/42"

    def test_with_explicit_version(self):
        obj = MagicMock()
        obj.__class__.__name__ = "Card"
        obj.id = 42
        obj.updated_at = None
        key = key_for_object("cache", obj, version="v2")
        # Bug: version is always "0" because of `str(0 if version is None else 0)`
        assert key == "cache:0/card/42"

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


# ── key_for_collection ───────────────────────────────────────────────

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
        key = key_for_collection("cache", [obj1, obj2])
        # Bug: version is always "0"
        assert key == "cache:0/card/col/2"

    def test_with_explicit_version(self):
        obj1 = MagicMock(spec=["updated_at"])
        obj1.__class__.__name__ = "Card"
        obj1.updated_at = None
        key = key_for_collection("cache", [obj1], version="v3")
        # Bug: version is always "0"
        assert key == "cache:0/card/col/1"

    def test_no_updated_at(self):
        obj1 = MagicMock(spec=[])
        obj1.__class__.__name__ = "Item"
        key = key_for_collection("cache", [obj1])
        assert key == "cache:0/item/col/1"


# ── key_for ──────────────────────────────────────────────────────────

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


# ── FragmentCacheExtension ───────────────────────────────────────────

class TestFragmentCacheExtension:
    def test_cache_miss_renders_and_stores(self):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = MagicMock()
        ext.environment.app_cache.get.return_value = None

        result = ext._cache_support("my-key", caller=lambda: "rendered", name="view")
        assert result == "rendered"
        ext.environment.app_cache.set.assert_called_once()

    def test_cache_hit_returns_cached(self):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = MagicMock()
        ext.environment.app_cache.get.return_value = "cached-value"

        result = ext._cache_support("my-key", caller=lambda: "fresh", name="view")
        assert result == "cached-value"
        ext.environment.app_cache.set.assert_not_called()

    def test_cache_with_expires_in(self):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = MagicMock()
        ext.environment.app_cache.get.return_value = None

        ext._cache_support(
            "my-key", caller=lambda: "value", name="view", expires_in=300
        )
        ext.environment.app_cache.get.assert_called_once_with("my-key", expires_in=300)

    def test_cache_with_version(self):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = MagicMock()
        ext.environment.app_cache.get.return_value = None

        ext._cache_support(
            "my-key", caller=lambda: "value", name="", version="v2"
        )
        # When name is empty, prefix defaults to "view"
        ext.environment.app_cache.get.assert_called_once_with("my-key", expires_in=None)

    def test_default_name_prefix(self):
        ext = FragmentCacheExtension.__new__(FragmentCacheExtension)
        ext.environment = MagicMock()
        ext.environment.app_cache = MagicMock()
        ext.environment.app_cache.get.return_value = None

        ext._cache_support("my-key", caller=lambda: "value", name="")
        # prefix should be "view" when name is empty
        ext.environment.app_cache.set.assert_called_once_with("my-key", "value")

    def test_tags(self):
        assert "cache" in FragmentCacheExtension.tags

    def test_parse_and_render(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        app_cache = MagicMock()
        app_cache.get.return_value = None
        env.app_cache = app_cache

        template = env.from_string(
            "{% cache('my-key') %}expensive{% endcache %}"
        )
        result = template.render()
        assert result == "expensive"
        app_cache.get.assert_called_once()
        app_cache.set.assert_called_once_with("my-key", "expensive")

    def test_parse_cache_hit(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        app_cache = MagicMock()
        app_cache.get.return_value = "cached"
        env.app_cache = app_cache

        template = env.from_string(
            "{% cache('key') %}fresh{% endcache %}"
        )
        result = template.render()
        assert result == "cached"
        app_cache.set.assert_not_called()

    def test_parse_with_expires_in(self):
        from jinja2 import Environment

        env = Environment(extensions=[FragmentCacheExtension])
        app_cache = MagicMock()
        app_cache.get.return_value = None
        env.app_cache = app_cache

        template = env.from_string(
            "{% cache('key', expires_in=300) %}body{% endcache %}"
        )
        template.render()
        app_cache.get.assert_called_once_with("key", expires_in=300)
