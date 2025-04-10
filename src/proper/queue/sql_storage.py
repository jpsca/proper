import typing as t

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
    database: pw.Database
    KV : type[pw.Model]
    Schedule : type[pw.Model]
    Task : type[pw.Model]

    def __init__(self, name: str, database: str | pw.Database, **kwargs):
        self.ready = False
        self.name = name
        if isinstance(database, pw.Database):
            self.database = database
        else:
            # Treat the database argument as a URL connection string.
            self.database = db_url_connect(database, **kwargs)

        assert isinstance(self.database, pw.Database)

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.close()
            self.database.connect()

        if not self.ready:
            self.create_models()
            self.create_tables()
            self.ready = True

    def create_models(self) -> None:  # type: ignore
        class Base(pw.Model):
            class Meta:
                database = self.database

        class QueueKV(Base):
            queue = pw.CharField()
            key = pw.CharField()
            value = BytesBlobField()

            class Meta:  # type: ignore
                primary_key = pw.CompositeKey("queue", "key")
                table_name = "queue_kv"

        self.KV = QueueKV

        class QueueSchedule(Base):
            queue = pw.CharField()
            data = BytesBlobField()
            timestamp = pw.TimestampField(resolution=1000)

            class Meta:  # type: ignore
                table_name = "queue_schedule"

        QueueSchedule.add_index(QueueSchedule.queue, QueueSchedule.timestamp, unique=False)
        self.Schedule = QueueSchedule

        class QueueTask(Base):
            queue = pw.CharField()
            uuid = pw.UUIDField(index=True)
            data = BytesBlobField()
            priority = pw.FloatField(default=0.0)

            class Meta:  # type: ignore
                table_name = "queue_task"

        QueueTask.add_index(QueueTask.priority.desc(), QueueTask.id)  # type: ignore
        self.Task = QueueTask

    def create_tables(self):
        with self.database:
            self.database.create_tables([self.KV, self.Schedule, self.Task])

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
        database: str,
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
        database: str,
        **options,
    ):
        options.setdefault("timeout", 10)
        db = pw.PostgresqlDatabase(database, **options)
        super().__init__(name, database=db)
