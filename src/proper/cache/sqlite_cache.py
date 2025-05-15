import typing as t
from time import time

import peewee as pw
from playhouse.sqlite_ext import SqliteExtDatabase

from .base import BaseCache, SerializerProtocol


class Cache(pw.Model):
    key = pw.TextField(primary_key=True)
    value = pw.BlobField()
    timestamp = pw.IntegerField(index=True)

    class Meta:
        table_name = "proper_cache"


class SqliteCache(BaseCache):
    """A simple Sqlite based cache"""
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
        self.database = self.db_class(database, pragmas=pragmas, timeout=timeout)
        for model in self.models:
            model.bind(self.database)

    def reset(self):
        # TBD: implement reset
        pass

    def close(self):
        return self.database.close()

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.connect()

    def create_tables(self):
        self.check_conn()
        with self.database.atomic():
            self.database.create_tables(self.models, safe=True)

    def set(self, key: str, value: t.Any, *, timestamp: int | None = None) -> None:
        self.check_conn()

        data = self.serialize(value)
        timestamp = int(time()) if timestamp is None else timestamp
        Cache.replace(key=key, value=data, timestamp=timestamp).execute()

    def get(self, key: str, *, expires_in: int | None = None) -> t.Any:
        self.check_conn()

        with self.database.atomic():
            row = Cache.get_or_none(Cache.key == key)
            if row is None:
                return None

            if expires_in is None:
                expires_in = self.expires_in
            curr_time = int(time())
            if (row.timestamp + expires_in) < curr_time:
                Cache.delete_by_id(key)
                return None

            return self.deserialize(row.value)

    def delete(self, key: str) -> None:
        self.check_conn()

        Cache.delete_by_id(key)

    def delete_expired(self, expires_in: int | None = None) -> None:
        self.check_conn()

        if expires_in is None:
            expires_in = self.expires_in
        expires_at = int(time()) - expires_in
        Cache.delete().where(Cache.timestamp < expires_at).execute()  # type: ignore

    def _count(self):
        return Cache.select(pw.fn.COUNT(Cache.key)).scalar()

