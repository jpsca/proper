import typing as t

import peewee as pw
from huey.api import Result, ResultGroup

from .base import BaseQueue
from .consumer import Consumer
from .sql_storage import PostgresStorage, SqliteStorage, SqlStorage


SIGNAL_CREATED = "created"


class SqlQueue(BaseQueue):
    """
    Arguments:

    - database: connection string
    - results: whether to store task results.
    - store_none: whether to store `None` in the result store
    - utc: use UTC internally by converting from local time.
    - immediate: useful for debugging; causes tasks to be executed
        synchronously in the application.
    - immediate_use_memory: automatically switch to a local in-memory
            storage backend when immediate-mode is enabled.

    """
    storage_class = SqlStorage

    def __init__(
        self,
        *,
        database: str | pw.Database,
        results: bool = True,
        store_none: bool = False,
        utc: bool = True,
        immediate: bool = False,
        immediate_use_memory: bool = True,
        **storage_kwargs,
    ):
        super().__init__(
            name="proper",
            database=database,
            results=results,
            store_none=store_none,
            utc=utc,
            immediate=immediate,
            immediate_use_memory=immediate_use_memory,
            **storage_kwargs
        )

    @property
    def database(self) -> pw.Database | None:
        if not self.storage:
            raise RuntimeError("Storage not initialized.")
        return self.storage.database  # type: ignore

    def enqueue(self, task):
        if task.expires:
            task.resolve_expires(self.utc)

        if self._immediate:
            self.execute(task)
        else:
            self.storage.enqueue(task, self.serialize_task(task))
            self._emit(SIGNAL_CREATED, task)

        if not self.results:
            return

        if task.on_complete:
            current_task = task
            results = []
            while current_task is not None:
                results.append(Result(self, current_task))
                current_task = current_task.on_complete
            return ResultGroup(results)
        else:
            return Result(self, task)

    def dequeue(self, callback: t.Callable):  # type: ignore
        self.storage.dequeue(callback)  # type: ignore

    def create_consumer(self, **options):
        self.storage.check_conn()  # type: ignore
        return Consumer(self, **options)


class SqliteQueue(SqlQueue):
    storage_class = SqliteStorage


class PostgreQueue(SqlQueue):
    storage_class = PostgresStorage
