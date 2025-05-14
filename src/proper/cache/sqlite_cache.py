import typing as t
from time import time

import peewee as pw

from proper.types import TPwJournalMode, TPwSyncMode, TPwWalCheckpoint

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

    def __init__(
        self,
        database: pw.SqliteDatabase,
        *,
        expires_in: int = 60 * 60 * 24 * 2,  # 2 days
        wal_checkpoint: TPwWalCheckpoint = "full",
        serializer: SerializerProtocol | None = None,
        sync_mode: TPwSyncMode = "normal",
        journal_mode: TPwJournalMode = "wal",
        vacuum_pages: int = 100,
        timeout: int = 5,
        **pragmas,
    ):
        super().__init__(serializer=serializer)
        self.expires_in = expires_in
        self.wal_checkpoint = wal_checkpoint.lower()
        pragmas.setdefault("auto_vacuum", "incremental")
        pragmas.setdefault("synchronous", sync_mode.lower())
        pragmas.setdefault("journal_mode", journal_mode.lower())
        pragmas.setdefault("incremental_vacuum", vacuum_pages)
        database._pragmas = list(pragmas.items())
        database._timeout = timeout
        self.database = database
        for model in self.models:
            model.bind(database)

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
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

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
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def delete_expired(self, expires_in: int | None = None) -> None:
        self.check_conn()

        if expires_in is None:
            expires_in = self.expires_in
        expires_at = int(time()) - expires_in
        Cache.delete().where(Cache.timestamp < expires_at).execute()  # type: ignore
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def _count(self):
        return Cache.select(pw.fn.COUNT(Cache.key)).scalar()

