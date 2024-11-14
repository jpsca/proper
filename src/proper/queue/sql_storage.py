import typing as t
from pathlib import Path

import peewee as pw
from huey.contrib.sql_huey import SqlStorage as HueySqlStorage
from playhouse.db_url import connect as db_url_connect

from proper.types import TPwSyncMode


class BytesBlobField(pw.BlobField):
    def python_value(self, value):
        if value is None:
            return None
        return value if isinstance(value, bytes) else bytes(value)


class SqlStorage(HueySqlStorage):
    KV : type[pw.Model]
    Schedule : type[pw.Model]
    Task : type[pw.Model]

    def __init__(self, name: str, database: str | pw.Database, **kwargs):
        self.name = name
        if isinstance(database, pw.Database):
            self.database = database
        else:
            # Treat the database argument as a URL connection string.
            self.database = db_url_connect(database, **kwargs)
        self.create_models()
        self.create_tables()
        # TODO: migrations

    def create_models(self) -> tuple:  # type: ignore
        class Base(pw.Model):
            class Meta:
                database = self.database

        class KV(Base):
            queue = pw.CharField()
            key = pw.CharField()
            value = BytesBlobField()

            class Meta:  # type: ignore
                primary_key = pw.CompositeKey("queue", "key")
                table_name = "proper_kv"

        self.KV = KV

        class Schedule(Base):
            queue = pw.CharField()
            data = BytesBlobField()
            timestamp = pw.TimestampField(resolution=1000)

            class Meta:  # type: ignore
                table_name = "proper_schedule"

        Schedule.add_index(Schedule.queue, Schedule.timestamp, unique=False)
        self.Schedule = Schedule

        class Task(Base):
            queue = pw.CharField()
            uuid = pw.UUIDField(index=True)
            data = BytesBlobField()
            priority = pw.FloatField(default=0.0)

            class Meta:  # type: ignore
                table_name = "proper_task"

        Task.add_index(Task.priority.desc(), Task.id)  # type: ignore
        self.Task = Task

        return (KV, Schedule, Task)

    def enqueue(self, task, data):  # type: ignore
        self.check_conn()
        self.Task.create(
            queue=self.name,
            uuid=task.id,
            data=data,
            priority=task.priority or 0,
        )

    def dequeue(self, callback: t.Callable):  # type: ignore
        self.check_conn()
        query = (
            self.tasks(self.Task.id, self.Task.data)  # type: ignore
            .order_by(self.Task.priority.desc(), self.Task.id)  # type: ignore
            .limit(1)
        )
        if self.database.for_update:
            query = query.for_update("FOR UPDATE SKIP LOCKED")

        with self.database.atomic():
            try:
                task = query.get()
            except self.Task.DoesNotExist:  # type: ignore
                return

            callback(task.data)
            self.Task.delete().where(self.Task.id == task.id).execute()  # type: ignore


class SqliteStorage(SqlStorage):
    def __init__(
        self,
        name: str,
        *,
        database: str | Path = "storage/app_cache.sqlite",
        timeout: int = 5,
        sync_mode: TPwSyncMode = "off",
        **pragmas,
    ):
        # This is required.
        # WAL mode allows one or more readers to continue reading
        # while another connection writes to the database.
        pragmas["journal_mode"] = "wal"
        pragmas.setdefault("synchronous", sync_mode.lower())
        db = pw.SqliteDatabase(database, timeout=timeout, pragmas=pragmas)
        super().__init__(name, database=db)


class PostgresStorage(SqlStorage):
    def __init__(
        self,
        name: str,
        *,
        database: str | Path = "storage/app_cache.sqlite",
        **options,
    ):
        options.setdefault("timeout", 10)
        db = pw.PostgresqlDatabase(database, **options)
        super().__init__(name, database=db)
