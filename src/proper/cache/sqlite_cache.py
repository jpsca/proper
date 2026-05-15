import itertools
import typing as t
from time import time

import peewee as pw
from playhouse.sqlite_ext import SqliteExtDatabase

from .base import BaseCache, SerializerProtocol


class Cache(pw.Model):
    key = pw.TextField(primary_key=True)
    value = pw.BlobField()
    expires_at = pw.IntegerField(index=True)

    class Meta:
        table_name = "proper_cache"


class SqliteCache(BaseCache):
    """A simple Sqlite based cache"""
    _counter = itertools.count()
    models = [Cache]
    db_class: type[pw.Database] = SqliteExtDatabase
    memory_based: bool = False

    def __init__(
        self,
        database: str,
        *,
        expires_in: int = 60 * 60 * 24 * 2,  # 2 days
        serializer: SerializerProtocol | None = None,
        timeout: int = 5,
        **pragmas,
    ):
        super().__init__(serializer=serializer)
        self.expires_in = expires_in

        # WAL mode allows one or more readers to continue reading
        # while another connection writes to the database.
        pragmas["journal_mode"] = "wal"
        pragmas.setdefault("wal_checkpoint", "full")
        pragmas.setdefault("synchronous", "normal")
        pragmas.setdefault("auto_vacuum", "incremental")
        pragmas.setdefault("incremental_vacuum", 100)

        self.memory_based = database == ":memory:"
        uri = False
        if self.memory_based:
            # Use a named in-memory database with shared cache so all threads
            # accessing this instance share the same data.
            database = f"file:proper_cache_{next(self._counter)}?mode=memory&cache=shared"
            uri = True
        self.database = self.db_class(database, pragmas=pragmas, timeout=timeout, uri=uri)
        for model in self.models:
            model.bind(self.database)
        if self.memory_based:
            self.create_tables()

    def close(self):
        return self.database.close()

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.connect()
            if self.memory_based:
                with self.database.atomic():
                    self.database.create_tables(self.models, safe=True)

    def create_tables(self):
        self.check_conn()
        with self.database.atomic():
            self.database.create_tables(self.models, safe=True)

    def set(self, key: str, value: t.Any, *, expires_in: int | None = None) -> None:
        self.check_conn()

        data = self.serialize(value)
        if expires_in is None:
            expires_in = self.expires_in
        expires_at = int(time()) + expires_in
        Cache.replace(key=key, value=data, expires_at=expires_at).execute()

    def get(self, key: str) -> t.Any:
        self.check_conn()

        with self.database.atomic():
            row = Cache.get_or_none(Cache.key == key)
            if row is None:
                return None

            if row.expires_at < int(time()):
                Cache.delete_by_id(key)
                return None

            return self.deserialize(row.value)

    def get_or_set(
        self,
        key: str,
        default: t.Any,
        *,
        expires_in: int | None = None,
        race_condition_ttl: int | None = None,
    ) -> t.Any:
        self.check_conn()
        if expires_in is None:
            expires_in = self.expires_in

        with self.database.atomic():
            row = Cache.get_or_none(Cache.key == key)
            curr_time = int(time())

            if row is not None:
                if row.expires_at >= curr_time:
                    return self.deserialize(row.value)

                if race_condition_ttl and curr_time < row.expires_at + race_condition_ttl:
                    # Expired but within race window — extend stale entry
                    # so other callers return the old value while we recompute.
                    Cache.update(expires_at=curr_time + race_condition_ttl).where(
                        Cache.key == key
                    ).execute()

        if callable(default):
            default = default()
        self.set(key, default, expires_in=expires_in)
        return default

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        self.check_conn()

        with self.database.atomic():
            row = Cache.get_or_none(Cache.key == key)
            curr_time = int(time())
            if expires_in is None:
                expires_in = self.expires_in

            if row is None:
                new_value = value
            elif row.expires_at < curr_time:
                new_value = value
            else:
                current_value = self.deserialize(row.value)
                new_value = current_value + value

            expires_at = curr_time + expires_in
            data = self.serialize(new_value)
            Cache.replace(key=key, value=data, expires_at=expires_at).execute()
            return new_value

    def decrement(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        return self.increment(key, -value, expires_in=expires_in)

    def read_multi(self, *keys: str) -> dict[str, t.Any]:
        self.check_conn()

        result = {}
        curr_time = int(time())
        expired_keys = []

        with self.database.atomic():
            rows = Cache.select().where(Cache.key << keys)
            for row in rows:
                if row.expires_at < curr_time:
                    expired_keys.append(row.key)
                else:
                    result[row.key] = self.deserialize(row.value)

            if expired_keys:
                Cache.delete().where(Cache.key << expired_keys).execute()

        return result

    def write_multi(self, mapping: dict[str, t.Any], *, expires_in: int | None = None) -> None:
        self.check_conn()

        if expires_in is None:
            expires_in = self.expires_in
        expires_at = int(time()) + expires_in

        with self.database.atomic():
            for key, value in mapping.items():
                data = self.serialize(value)
                Cache.replace(key=key, value=data, expires_at=expires_at).execute()

    def delete(self, key: str) -> None:
        self.check_conn()

        Cache.delete_by_id(key)

    def clear(self) -> None:
        self.check_conn()
        Cache.delete().execute()

    def delete_expired(self) -> None:
        self.check_conn()

        curr_time = int(time())
        Cache.delete().where(Cache.expires_at < curr_time).execute()

    def _count(self):
        return Cache.select(pw.fn.COUNT(Cache.key)).scalar()

