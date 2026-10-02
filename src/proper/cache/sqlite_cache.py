import itertools
import typing as t
from time import sleep, time

import peewee as pw

from .base import BaseCache, SerializerProtocol


CONNECT_ATTEMPTS = 5


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
    db_class: type[pw.Database] = pw.SqliteDatabase
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

    def connect(self):
        # Setting the WAL mode of a new database fails with "database is
        # locked" if another process is doing the same at that moment.
        attempt = 1
        while True:
            try:
                self.database.connect()
                return
            except pw.OperationalError:
                if attempt == CONNECT_ATTEMPTS:
                    raise
                sleep(0.05 * attempt)
                attempt += 1

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.connect()
            # The cache creates its own table when it's missing, so a new
            # database works without running a migration first.
            if not all(model.table_exists() for model in self.models):
                self.create_tables()

    def create_tables(self):
        if not self.database.is_connection_usable():
            self.connect()
        # Takes the write lock from the start. When several processes open
        # a new database at once, the others wait instead of failing.
        with self.database.atomic("IMMEDIATE"):
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

        # No transaction here: one that reads and then writes fails with
        # "database is locked", without waiting, if another connection
        # wrote in between.
        row = Cache.get_or_none(Cache.key == key)
        if row is None:
            return None

        curr_time = int(time())
        if row.expires_at < curr_time:
            self._delete_expired_keys([key], curr_time)
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

        row = Cache.get_or_none(Cache.key == key)
        curr_time = int(time())

        if row is not None:
            if row.expires_at >= curr_time:
                return self.deserialize(row.value)

            if race_condition_ttl and curr_time < row.expires_at + race_condition_ttl:
                # Expired but within race window - extend stale entry
                # so other callers return the old value while we recompute.
                # Only the caller that extends it recomputes: the others
                # don't match the row as it was read.
                extended = (
                    Cache.update(expires_at=curr_time + race_condition_ttl)
                    .where(Cache.key == key, Cache.expires_at == row.expires_at)
                    .execute()
                )
                if not extended:
                    return self.deserialize(row.value)

        if callable(default):
            default = default()
        self.set(key, default, expires_in=expires_in)
        return default

    def increment(self, key: str, value: int = 1, *, expires_in: int | None = None) -> int:
        self.check_conn()

        # Takes the write lock before reading, so concurrent increments wait
        # for each other instead of failing or losing counts.
        with self.database.atomic("IMMEDIATE"):
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

        rows = Cache.select().where(Cache.key << keys)  # ty: ignore[unsupported-operator]
        for row in rows:
            if row.expires_at < curr_time:
                expired_keys.append(row.key)
            else:
                result[row.key] = self.deserialize(row.value)

        if expired_keys:
            self._delete_expired_keys(expired_keys, curr_time)

        return result

    def _delete_expired_keys(self, keys: list[str], curr_time: int) -> None:
        # The check of the date is repeated because the keys could have
        # been set again after they were read.
        Cache.delete().where(
            Cache.key << keys,  # ty: ignore[unsupported-operator]
            Cache.expires_at < curr_time,
        ).execute()

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
        Cache.delete().where(Cache.expires_at < curr_time).execute()  # ty: ignore[unsupported-operator]

    def _count(self):
        return Cache.select(pw.fn.COUNT(Cache.key)).scalar()

