import typing as t
from pathlib import Path
from time import time

import peewee as pw

from .base import BaseCache, Serializer


TWalCheckpoint = (
    t.Literal["passive"]
    | t.Literal["full"]
    | t.Literal["restart"]
    | t.Literal["truncate"]
)

TSyncMode = (
    t.Literal["extra"] | t.Literal["full"] | t.Literal["normal"] | t.Literal["off"]
)


class SqliteCache(BaseCache):
    """A simple Sqlite based cache"""

    def __init__(
        self,
        database: str | Path = "storage/app_cache.sqlite",
        *,
        timeout: int = 60 * 60 * 24 * 5,  # 5 days
        sync_mode: TSyncMode = "normal",
        wal_checkpoint: TWalCheckpoint = "full",
        vacuum_pages: int = 100,
        serializer_cls: type[Serializer] | None = None,
        **options,
    ):
        super().__init__(serializer_cls=serializer_cls)
        self.timeout = timeout

        self.wal_checkpoint = wal_checkpoint.lower()
        options.setdefault("timeout", 60)
        options["pragmas"] = {
            "auto_vacuum": "incremental",
            "synchronous": sync_mode.lower(),
            "journal_mode": "wal",
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
            expire = pw.IntegerField(index=True)

            class Meta:
                table_name = "proper_cache"

        self.Cache = Cache

    def create_tables(self):
        with self.database:
            self.database.create_tables([self.Cache])

    def drop_tables(self):
        with self.database:
            self.database.drop_tables([self.Cache])

    def close(self):
        return self.database.close()

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.close()
            self.database.connect()

    def get(self, key: str) -> t.Any:
        self.check_conn()

        with self.database.atomic():
            row = self.Cache.get_or_none(self.Cache.key == key)
            if row is None:
                return None

            curr_time = int(time())
            if row.expire < curr_time:
                self.Cache.delete_by_id(key)
                return None

            return self.deserialize(row.value)

    def set(self, key: str, value: t.Any, timeout: int | None = None) -> None:
        self.check_conn()

        if timeout is None:
            timeout = self.timeout
        expire = int(time()) + timeout
        data = self.serialize(value)
        self.Cache.replace(key=key, value=data, expire=expire).execute()
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def delete(self, key: str) -> None:
        self.check_conn()
        self.Cache.delete_by_id(key)
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)

    def delete_expired(self) -> None:
        self.check_conn()
        curr_time = int(time())
        self.Cache.delete().where(self.Cache.expire < curr_time).execute()
        self.database.pragma("wal_checkpoint", self.wal_checkpoint)
