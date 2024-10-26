from proper.cache import SqliteCache


def test_set_get(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key", "value")
    assert "value" == cache.get("key")


def test_get_invalid(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key", "value")
    assert cache.get("foo") is None


def test_set_replaces(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key", "value")
    cache.set("key", "value2")
    assert cache.count() == 1
    assert "value2" == cache.get("key")


def test_get_expired_is_deleted(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key", "value", timeout=-1)
    assert cache.count() == 1
    assert cache.get("key") is None
    assert cache.count() == 0
    assert cache.get("key") is None


def test_delete(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key", "value")
    assert cache.count() == 1
    cache.delete("key")
    assert cache.count() == 0
    assert cache.get("key") is None


def test_delete_expired(tmp_path):
    cache = SqliteCache(tmp_path / "cache.sqlite")

    cache.set("key1", "value1", timeout=-1)
    cache.set("key2", "value2", timeout=-1)
    cache.set("key3", "value3", timeout=1000)
    cache.set("key4", "value4", timeout=-1)
    assert cache.count() == 4
    cache.delete_expired()
    assert cache.count() == 1
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") == "value3"
    assert cache.get("key4") is None
