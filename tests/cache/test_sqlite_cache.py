from time import time

from playhouse.sqlite_ext import SqliteExtDatabase

from proper.cache import SqliteCache


def test_set_get(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key", "value")
    assert "value" == cache.get("key")


def test_get_not_found(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key", "value")
    assert cache.get("foo") is None


def test_set_replaces(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key", "value")
    cache.set("key", "value2")
    assert cache._count() == 1
    assert "value2" == cache.get("key")


def test_get_expired_is_deleted(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key", "value")
    assert cache._count() == 1
    assert cache.get("key", expires_in=-1) is None
    assert cache._count() == 0
    assert cache.get("key", expires_in=-1) is None


def test_get_expired_is_deleted_with_default(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database, expires_in=-1)
    cache.create_tables()

    cache.set("key", "value")
    assert cache._count() == 1
    assert cache.get("key") is None
    assert cache._count() == 0
    assert cache.get("key") is None


def test_delete(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key", "value")
    assert cache._count() == 1
    cache.delete("key")
    assert cache._count() == 0
    assert cache.get("key") is None


def test_delete_expired(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database)
    cache.create_tables()

    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3", timestamp=int(time()) + 2)
    cache.set("key4", "value4")
    assert cache._count() == 4
    cache.delete_expired(expires_in=-1)
    assert cache._count() == 1
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") == "value3"
    assert cache.get("key4") is None


def test_delete_expired_with_default(tmp_path):
    database = SqliteExtDatabase(tmp_path / "cache.sqlite")
    cache = SqliteCache(database, expires_in=-1)
    cache.create_tables()

    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3", timestamp=int(time()) + 2)
    cache.set("key4", "value4")
    assert cache._count() == 4
    cache.delete_expired()
    assert cache._count() == 1
    assert cache.get("key1") is None
    assert cache.get("key2") is None
    assert cache.get("key3") == "value3"
    assert cache.get("key4") is None
