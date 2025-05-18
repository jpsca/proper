import peewee as pw
from huey.api import Result, ResultGroup
from huey.consumer import Consumer

from .base import BaseQueue
from .sql_storage import PostgresStorage, SqliteStorage, SqlStorage


SIGNAL_CREATED = "created"


class SqlQueue(BaseQueue):
    """
    Arguments:

    - database: database instance to use.
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
        database: pw.Database,
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
    def models(self) -> list[type[pw.Model]] | None:
        if not self.storage:
            raise RuntimeError("Storage not initialized.")
        return getattr(self.storage, "models", None)

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

    def create_consumer(self, **options) -> Consumer:  # type: ignore
        if hasattr(self.storage, "check_conn"):
            self.storage.check_conn()   # type: ignore
        print("Creating consumer", options)
        consumer = Consumer(self, **options)
        return consumer


class SqliteQueue(SqlQueue):
    storage_class = SqliteStorage


class PostgreQueue(SqlQueue):
    storage_class = PostgresStorage
