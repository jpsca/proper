import time
import unittest.mock

import pytest

from proper.cache import RedisCache


@pytest.fixture()
def cache(redis_url):
    c = RedisCache(url=redis_url, expires_in=60)
    c.clear()
    yield c
    c.close()



class TestSetGet:
    def test_set_and_get(self, cache):
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self, cache):
        assert cache.get("nonexistent") is None

    def test_set_overwrites(self, cache):
        cache.set("key1", "first")
        cache.set("key1", "second")
        assert cache.get("key1") == "second"

    def test_complex_value(self, cache):
        obj = {"list": [1, 2, 3], "nested": {"a": True}}
        cache.set("complex", obj)
        assert cache.get("complex") == obj

    def test_custom_expires_in(self, cache):
        cache.set("key1", "value1", expires_in=3600)
        assert cache.get("key1") == "value1"



class TestGetOrSet:
    def test_miss(self, cache):
        result = cache.get_or_set("key", "default")
        assert result == "default"
        assert cache.get("key") == "default"

    def test_hit(self, cache):
        cache.set("key", "existing")
        result = cache.get_or_set("key", "default")
        assert result == "existing"

    def test_callable(self, cache):
        called = []
        result = cache.get_or_set("key", lambda: (called.append(1), "computed")[1])
        assert result == "computed"
        assert len(called) == 1

    def test_callable_not_called_on_hit(self, cache):
        cache.set("key", "existing")
        called = []
        cache.get_or_set("key", lambda: called.append(1) or "new")
        assert len(called) == 0

    def test_race_condition_ttl_in_window(self, cache):
        """Key about to expire - extends stale and recomputes."""
        # Set with very short TTL so Redis TTL is low
        cache.set("key", "stale", expires_in=2)
        time.sleep(1)  # let TTL drop into the race window

        result = cache.get_or_set(
            "key", lambda: "fresh", expires_in=60, race_condition_ttl=10,
        )
        assert result == "fresh"
        assert cache.get("key") == "fresh"

    def test_race_condition_ttl_miss(self, cache):
        """Key fully expired - normal recompute."""
        result = cache.get_or_set(
            "gone", lambda: "new", expires_in=60, race_condition_ttl=10,
        )
        assert result == "new"

    def test_race_condition_ttl_not_in_window(self, cache):
        """Key still valid (TTL well above window) - returns cached."""
        cache.set("key", "valid", expires_in=3600)
        called = []
        result = cache.get_or_set(
            "key", lambda: called.append(1), race_condition_ttl=10,
        )
        assert result == "valid"
        assert len(called) == 0



class TestIncrementDecrement:
    def test_increment_new_key(self, cache):
        assert cache.increment("counter") == 1

    def test_increment_existing(self, cache):
        cache.increment("counter")
        assert cache.increment("counter") == 2

    def test_increment_custom_value(self, cache):
        cache.increment("counter", 5)
        assert cache.increment("counter", 3) == 8

    def test_decrement(self, cache):
        cache.increment("counter", 10)
        assert cache.decrement("counter") == 9
        assert cache.decrement("counter", 4) == 5

    def test_increment_custom_ttl(self, cache):
        cache.increment("counter", 1, expires_in=3600)
        assert cache.increment("counter", 1, expires_in=3600) == 2

    def test_increment_retries_on_watch_error(self, cache):
        """Concurrent modification between WATCH and EXEC triggers retry."""
        cache.increment("counter", 10)  # start at 10

        # After the first WATCH+GET, sneak in a write from another client
        # so the transaction fails, then let the retry succeed.
        original_get = cache.client.pipeline().__class__.get
        calls = []

        def intercepting_get(pipe_self, key):
            result = original_get(pipe_self, key)
            if not calls:
                calls.append(1)
                # Concurrent writer changes the key outside the pipeline
                cache.client.set(key, cache.serialize(99))
            return result

        with unittest.mock.patch.object(
            cache.client.pipeline().__class__, "get", intercepting_get
        ):
            result = cache.increment("counter", 1)

        # The retry should read 99 and return 100
        assert result == 100
        assert cache.get("counter") == 100



class TestDeleteClear:
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

    def test_delete_expired_is_noop(self, cache):
        cache.delete_expired()  # Redis handles TTLs natively



class TestMulti:
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
        cache.write_multi({})  # should not raise



class TestConfig:
    def test_custom_expires_in(self, redis_url):
        c = RedisCache(url=redis_url, expires_in=10)
        assert c.expires_in == 10
        c.close()

    def test_close(self, redis_url):
        c = RedisCache(url=redis_url)
        c.close()  # should not raise

    def test_import_error_when_redis_missing(self, monkeypatch):
        import proper.cache.redis_cache as mod
        monkeypatch.setattr(mod, "redis", None)
        with pytest.raises(ImportError, match="redis is required"):
            RedisCache()
