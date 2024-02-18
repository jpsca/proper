import sqlite3
import typing as t
from pathlib import Path
from time import time

from proper.helpers import jsonplus, logger

from .base import BaseCache


TWalCheckpoint = (
    t.Literal["PASSIVE"]
    | t.Literal["FULL"]
    | t.Literal["RESTART"]
    | t.Literal["TRUNCATE"]
)

TSyncMode = (
    t.Literal["EXTRA"] | t.Literal["FULL"] | t.Literal["NORMAL"] | t.Literal["OFF"]
)


class SqliteCache(BaseCache):
    """A simple Sqlite based cache"""

    # prepared queries for cache operations
    _pragma_wal = "PRAGMA journal_mode = WAL"
    _pragma_vacuum = "PRAGMA auto_vacuum = incremental;"
    _pragma_sync = "PRAGMA synchronous = ?"
    _pragma_checkpoint = "PRAGMA wal_checkpoint(?)"
    _pragma_incr_vacuum = "PRAGMA incremental_vacuum(?)"

    _sql_create = (
        "CREATE TABLE IF NOT EXISTS cache "
        "( key TEXT PRIMARY KEY, val TEXT, exp FLOAT )"
    )
    _sql_index = "CREATE INDEX IF NOT EXISTS keyname_index ON cache (key)"

    _sql_select = "SELECT val, exp FROM cache WHERE key = ?"
    _sql_insert = "INSERT INTO cache (key, val, exp) VALUES (?, jsonb(?), ?)"
    _sql_update = "REPLACE INTO cache (key, val, exp) VALUES (?, jsonb(?), ?)"
    _sql_delete = "DELETE FROM cache WHERE key = ?"
    _sql_expire = "DELETE FROM cache WHERE exp < ?"

    # other properties
    connection = None

    def __init__(
        self,
        path: str | Path,
        *,
        name: str = "cache.sqlite",
        sync_mode: TSyncMode = "NORMAL",
        wal_checkpoint: TWalCheckpoint = "FULL",
        vacuum_pages: int = 100,
        **options,
    ):
        path = Path(path).resolve()
        if path.is_file():
            name = path.name
            path = path.parent

        path.mkdir(exist_ok=True, parents=True)
        self.path = str(path / name)
        logger.debug("Created/Verified the storage path for %s", self.path)

        self.sync_mode = sync_mode
        self.wal_checkpoint = wal_checkpoint
        self.vacuum_pages = vacuum_pages

        options.setdefault("timeout", 60)
        self.options = options

    def get(self, key: str) -> t.Any:
        curr_time = time()
        return_value = None

        with self._get_conn() as conn:
            for row in conn.execute(self._sql_select, (key,)):
                expire = row[1]
                if expire == 0 or expire > curr_time:
                    return_value = jsonplus.loads(str(row[0]))["_"]
                break

        return return_value

    def set(self, key: str, value: t.Any, timeout: int | float) -> None:
        expire = time() + timeout
        value = {"_": value}
        data = jsonplus.dumps(value)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(self._sql_insert, (key, data, expire))
            except sqlite3.IntegrityError:
                logger.debug("Key %s exists. Falling back to update", key)
                cursor.execute(self._sql_update, (key, data, expire))

            cursor.execute(self._pragma_checkpoint, (self.wal_checkpoint,))

    def update(self, key: str, value: t.Any, timeout: int | float) -> None:
        expire = time() + timeout
        value = {"data": value}
        data = jsonplus.dumps(value)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql_update, (key, data, expire))
            cursor.execute(self._pragma_checkpoint, (self.wal_checkpoint,))

    def delete(self, key: str) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql_delete, (key,))

    def delete_expired(self) -> None:
        curr_time = time()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(self._sql_expire, (curr_time,))
            cursor.execute(self._pragma_incr_vacuum, (self.vacuum_pages,))

    # Private

    def _get_conn(self):
        """Returns a Sqlite connection"""
        if self.connection:
            return self.connection

        # setup the connection
        conn = sqlite3.Connection(self.path, **self.options)
        logger.debug("Connected to %s", self.path)

        # Running the PRAGMAS
        with conn:
            cursor = conn.cursor()
            cursor.execute(self._pragma_wal)
            mode = cursor.fetchone()[0].lower()
            if mode != "wal":
                logger.warning("Unable to activate the WAL journal mode")
            else:
                logger.debug("Activated WAL journal mode")

            cursor.execute(self._pragma_sync, (self.sync_mode,))
            logger.debug("Activated %s sync mode", self.sync_mode)

            cursor.execute(self._pragma_vacuum)
            logger.debug("Activated incremental auto-vacuum")

        # ensure that the table schema is available
        with conn:
            cursor = conn.cursor()
            cursor.execute(self._sql_create)
            cursor.execute(self._sql_index)
            logger.debug("Ran the create SQL script")

        self.connection = conn
        return self.connection
