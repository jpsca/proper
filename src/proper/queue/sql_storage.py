"""
Adapted from `huey.contrib.sql_huey.SqlStorage` from the Huey library.
(https://github.com/coleifer/huey)
Used with permission under the MIT license.
"""

import operator
import typing as t

import peewee as pw
from huey.constants import EmptyData
from huey.storage import BaseStorage
from playhouse.db_url import connect as db_url_connect

from proper.types import TPwSyncMode


class BytesBlobField(pw.BlobField):
    def python_value(self, value):
        if value is None:
            return None
        return value if isinstance(value, bytes) else bytes(value)


class SqlStorage(BaseStorage):
    database: pw.Database
    KV: type[pw.Model]
    Schedule: type[pw.Model]
    Task: type[pw.Model]

    for_update = True

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

        QueueSchedule.add_index(
            QueueSchedule.queue, QueueSchedule.timestamp, unique=False
        )
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

    def close(self):
        self.database.close()

    def tasks(self, *columns):
        return (
            self.Task.select(*columns)
            .where(self.Task.queue == self.name)  # type: ignore
        )

    def schedule(self, *columns):
        return (
            self.Schedule.select(*columns)
            .where(self.Schedule.queue == self.name)  # type: ignore
        )

    def kv(self, *columns):
        return (
            self.KV.select(*columns)
            .where(self.KV.queue == self.name)  # type: ignore
        )

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
        if self.for_update:
            query = query.for_update("FOR UPDATE SKIP LOCKED")

        with self.database.atomic():
            try:
                task = query.get()
            except self.Task.DoesNotExist:  # type: ignore
                return

            callback(task.data)
            self.Task.delete().where(self.Task.id == task.id).execute()  # type: ignore

    def queue_size(self):
        return self.tasks().count()

    def enqueued_items(self, limit=None):
        query = (
            self.tasks(self.Task.data)  # type: ignore
            .order_by(self.Task.priority.desc(), self.Task.id)  # type: ignore
        )
        if limit is not None:
            query = query.limit(limit)
        return list(map(operator.itemgetter(0), query.tuples()))

    def flush_queue(self):
        (
            self.Task.delete()
            .where(self.Task.queue == self.name)  # type: ignore
            .execute()
        )

    def add_to_schedule(self, data, ts):
        self.check_conn()
        self.Schedule.create(queue=self.name, data=data, timestamp=ts)

    def read_schedule(self, ts):
        self.check_conn()
        query = (
            self.schedule(self.Schedule.id, self.Schedule.data)  # type: ignore
            .where(self.Schedule.timestamp <= ts)  # type: ignore
            .tuples()
        )
        if self.for_update:
            query = query.for_update()

        with self.database.atomic():
            results = list(query)
            if not results:
                return []

            id_list, data = zip(*results, strict=True)
            (
                self.Schedule.delete()
                .where(self.Schedule.id.in_(id_list))  # type: ignore
                .execute()
            )
            return list(data)

    def schedule_size(self):
        return self.schedule().count()

    def scheduled_items(self, limit: int | None = None):
        tasks = (
            self.schedule(self.Schedule.data)  # type: ignore
            .order_by(self.Schedule.timestamp)  # type: ignore
            .limit(limit)
            .tuples()
        )
        return list(map(operator.itemgetter(0), tasks))

    def flush_schedule(self):
        (
            self.Schedule.delete()
            .where(self.Schedule.queue == self.name)  # type: ignore
            .execute()
        )

    def put_data(self, key, value, is_result=False):
        self.check_conn()
        self.KV.replace(queue=self.name, key=key, value=value).execute()

    def peek_data(self, key):
        self.check_conn()
        try:
            kv = (
                self.kv(self.KV.value)  # type: ignore
                .where(self.KV.key == key)  # type: ignore
                .get()
            )
        except self.KV.DoesNotExist:  # type: ignore
            return EmptyData
        else:
            return kv.value

    def pop_data(self, key):
        self.check_conn()
        query = self.kv().where(self.KV.key == key)  # type: ignore
        if self.for_update:
            query = query.for_update()

        with self.database.atomic():
            try:
                kv = query.get()
            except self.KV.DoesNotExist:  # type: ignore
                return EmptyData
            else:
                dq = (
                    self.KV.delete()
                    .where(
                        (self.KV.queue == self.name)  # type: ignore
                        & (self.KV.key == key)  # type: ignore
                    )
                )
                return kv.value if dq.execute() == 1 else EmptyData

    def has_data_for_key(self, key):
        self.check_conn()
        return self.kv().where(self.KV.key == key).exists()  # type: ignore

    def put_if_empty(self, key, value):
        self.check_conn()
        try:
            with self.database.atomic():
                self.KV.insert(queue=self.name, key=key, value=value).execute()
        except pw.IntegrityError:
            return False
        else:
            return True

    def result_store_size(self):
        return self.kv().count()

    def result_items(self):
        query = self.kv(self.KV.key, self.KV.value).tuples()  # type: ignore
        return dict(query.iterator())

    def flush_results(self):
        (
            self.KV.delete()
            .where(self.KV.queue == self.name)  # type: ignore
            .execute()
        )


class SqliteStorage(SqlStorage):
    for_update = False

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
    for_update = True

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

    def put_data(self, key, value, is_result=False):
        self.check_conn()
        (
            self.KV.insert(queue=self.name, key=key, value=value)
            .on_conflict(
                conflict_target=[self.KV.queue, self.KV.key],  # type: ignore
                preserve=[self.KV.value]  # type: ignore
            )
            .execute()
        )
