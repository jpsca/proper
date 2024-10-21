import sqlite3
import typing as t
from pathlib import Path
from time import time

import peewee as pw
from playhouse.db_url import connect as db_url_connect

from proper.helpers import jsonplus, logger

from .base import BaseCache


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

    Cache: type[pw.Model]

    # prepared queries for cache operations
    _pragma_vacuum = "PRAGMA auto_vacuum = incremental;"
    _pragma_wal = "PRAGMA journal_mode = WAL;"
    _pragma_sync = "PRAGMA synchronous = ?;"
    _pragma_checkpoint = "PRAGMA wal_checkpoint(?);"
    _pragma_incr_vacuum = "PRAGMA incremental_vacuum(?);"

    _sql_select = "SELECT val, ts, exp FROM cache WHERE key = ?;"
    _sql_insert = "INSERT INTO cache (key, val, ts, exp) VALUES (?, jsonb(?), ?, ?);"
    _sql_update = "REPLACE INTO cache (key, val, ts, exp) VALUES (?, jsonb(?), ?, ?);"
    _sql_delete = "DELETE FROM cache WHERE key = ?;"
    _sql_expire = "DELETE FROM cache WHERE exp < ?;"

    # other properties
    connection = None

    def __init__(
        self,
        database: str | Path = "storage/app_cache.sqlite",
        *,
        sync_mode: TSyncMode = "normal",
        wal_checkpoint: TWalCheckpoint = "full",
        vacuum_pages: int = 100,
        **options,
    ):
        self.sync_mode = sync_mode.lower()
        self.wal_checkpoint = wal_checkpoint.lower()
        self.vacuum_pages = vacuum_pages
        options.setdefault("timeout", 60)
        self.options = options

        database = Path(database).resolve()
        database.parent.mkdir(exist_ok=True, parents=True)
        self.database = db_url_connect(database)

        self.create_models()
        self.create_tables()

    def create_models(self) -> tuple:  # type: ignore
        class Base(pw.Model):
            class Meta:
                database = self.database

        class Cache(Base):
            key = pw.TextField(primary_key=True)
            val = pw.TextField()
            ts = pw.FloatField()
            exp = pw.FloatField(index=True)

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
        curr_time = time()
        return_value = None

        conn = self._get_connection()
        for row in conn.execute(self._sql_select, (key,)):
            expire = row[-1]
            if expire == 0 or expire > curr_time:
                return_value = jsonplus.loads(str(row[0]))["_"]
            break

        return return_value

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        ts = time()
        expire = ts + timeout
        value = {"_": value}
        data = jsonplus.dumps(value)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(self._sql_insert, (key, data, ts, expire))
        except sqlite3.IntegrityError:
            logger.debug("Key %s exists. Falling back to update", key)
            cursor.execute(self._sql_update, (key, data, ts, expire))
        cursor.execute(self._pragma_checkpoint, (self.wal_checkpoint,))

    def update(self, key: str, value: t.Any, timeout: int | float) -> None:
        ts = time()
        expire = ts + timeout
        value = {"data": value}
        data = jsonplus.dumps(value)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(self._sql_update, (key, data, ts, expire))
        cursor.execute(self._pragma_checkpoint, (self.wal_checkpoint,))

    def delete(self, key: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(self._sql_delete, (key,))

    def delete_expired(self) -> None:
        curr_time = time()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(self._sql_expire, (curr_time,))
        cursor.execute(self._pragma_incr_vacuum, (self.vacuum_pages,))

    # Private

    def _init_schema(self):
        conn = sqlite3.Connection(self.database, **self.options)
        cursor = conn.cursor()

        logger.debug("Activating incremental auto-vacuum")
        cursor.execute(self._pragma_vacuum)

        logger.debug("Running the create SQL script")
        cursor.execute(self._sql_create)
        cursor.execute(self._sql_index)

    def _get_connection(self):
        """Returns a Sqlite connection"""
        if self.connection:
            return self.connection

        # setup the connection
        self.connection = sqlite3.Connection(self.database, **self.options)
        logger.debug("Connected to %s", self.database)

        # Non-persistent PRAGMAs
        cursor = self.connection.cursor()

        logger.debug("Activating WAL journal mode")
        cursor.execute(self._pragma_wal)
        mode = cursor.fetchone()[0].lower()
        if mode != "wal":
            logger.warning("Unable to activate the WAL journal mode")

        logger.debug("Activating %s sync mode", self.sync_mode)
        cursor.execute(self._pragma_sync, (self.sync_mode,))

        return self.connection
