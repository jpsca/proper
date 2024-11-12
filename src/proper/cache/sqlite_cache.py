import typing as t
from pathlib import Path
from time import time

import peewee as pw

from .base import BaseCache, SerializerProtocol


TWalCheckpoint = (
    t.Literal["passive"]
    | t.Literal["full"]
    | t.Literal["restart"]
    | t.Literal["truncate"]
)

TSyncMode = (
    t.Literal["extra"]
    | t.Literal["full"]
    | t.Literal["normal"]
    | t.Literal["off"]
)

TJournalMode = (
    t.Literal["delete"]
    | t.Literal["truncate"]
    | t.Literal["persist"]
    | t.Literal["memory"]
    | t.Literal["wal"]
    | t.Literal["off"]
)


class SqliteCache(BaseCache):
    """A simple Sqlite based cache"""

    def __init__(
        self,
        database: str | Path = "storage/app_cache.sqlite",
        *,
        expires_in: int = 60 * 60 * 24 * 2,  # 2 days
        sync_mode: TSyncMode = "normal",
        journal_mode: TJournalMode = "wal",
        wal_checkpoint: TWalCheckpoint = "full",
        vacuum_pages: int = 100,
        serializer: SerializerProtocol | None = None,
        **options,
    ):
        super().__init__(serializer=serializer)
        self.expires_in = expires_in
        self.wal_checkpoint = wal_checkpoint.lower()

        options.setdefault("timeout", 60)
        options["pragmas"] = {
            "auto_vacuum": "incremental",
            "synchronous": sync_mode.lower(),
            "journal_mode": journal_mode.lower(),
            "incremental_vacuum": vacuum_pages,
        }
        database = Path(database).resolve()
        database.parent.mkdir(exist_ok=True, parents=True)
        self.database = pw.SqliteDatabase(database, **options)
        self.create_models()
        self.create_tables()

    def create_models(self) -> tuple:  # type: ignore
        class Base(pw.Model):
            class Meta:
                database = self.database

        class Cache(Base):
            key = pw.TextField(primary_key=True)
            value = pw.BlobField()
            timestamp = pw.IntegerField(index=True)

            class Meta:  # type: ignore
                table_name = "proper_cache"

        self.Cache = Cache

    def create_tables(self):
        with self.database:
            self.database.create_tables([self.Cache])

    def drop_tables(self):
        with self.database:
            self.database.drop_tables([self.Cache])

    def reset(self):
        with self.database:
            self.database.drop_tables([self.Cache])
            self.database.create_tables([self.Cache])

    def close(self):
        return self.database.close()

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.close()
            self.database.connect()

    def set(self, key: str, value: t.Any, *, timestamp: int | None = None) -> None:
        self.check_conn()

        data = self.serialize(value)
        timestamp = int(time()) if timestamp is None else timestamp
        self.Cache.replace(key=key, value=data, timestamp=timestamp).execute()
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def get(self, key: str, *, expires_in: int | None = None) -> t.Any:
        self.check_conn()

        with self.database.atomic():
            row = self.Cache.get_or_none(self.Cache.key == key)
            if row is None:
                return None

            if expires_in is None:
                expires_in = self.expires_in
            curr_time = int(time())
            if (row.timestamp + expires_in) < curr_time:
                self.Cache.delete_by_id(key)
                return None

            return self.deserialize(row.value)

    def delete(self, key: str) -> None:
        self.check_conn()

        self.Cache.delete_by_id(key)
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def delete_expired(self, expires_in: int | None = None) -> None:
        self.check_conn()

        if expires_in is None:
            expires_in = self.expires_in
        expires_at = int(time()) - expires_in
        self.Cache.delete().where(self.Cache.timestamp < expires_at).execute()  # type: ignore
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def _count(self):
        return self.Cache.select(pw.fn.COUNT(self.Cache.key)).scalar()

