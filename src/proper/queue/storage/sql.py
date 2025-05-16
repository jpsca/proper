"""
Adapted from `huey.contrib.sql_huey.SqlStorage` from the Huey library.
(https://github.com/coleifer/huey)
Used with permission under the MIT license.
"""

import operator
import typing as t

import peewee as pw
from huey.constants import EmptyData
from playhouse.postgres_ext import PostgresqlExtDatabase
from playhouse.psycopg3_ext import Psycopg3Database
from playhouse.sqlite_ext import SqliteExtDatabase

from .base import BaseStorage


class BytesBlobField(pw.BlobField):
    def python_value(self, value):
        if value is None:
            return None
        return value if isinstance(value, bytes) else bytes(value)


class QueueKV(pw.Model):
    queue = pw.CharField()
    key = pw.CharField()
    value = BytesBlobField()

    class Meta:  # type: ignore
        primary_key = pw.CompositeKey("queue", "key")


class QueueSchedule(pw.Model):
    queue = pw.CharField()
    data = BytesBlobField()
    timestamp = pw.TimestampField(resolution=1000)

    class Meta:  # type: ignore
        indexes = [(("queue", "timestamp"), False)]


class QueueTask(pw.Model):
    queue = pw.CharField()
    uuid = pw.UUIDField(index=True)
    data = BytesBlobField()
    priority = pw.FloatField(default=0.0)
    done = pw.BooleanField(default=False)

    class Meta:  # type: ignore
        indexes = [(("done", "priority", "id"), False)]


class SqlStorage(BaseStorage):
    database: pw.Database
    db_class: type[pw.Database]
    models = [QueueKV, QueueSchedule, QueueTask]

    for_update: bool = True
    memory_based: bool = False

    def __init__(
            self,
            name: str,
            database: str,
            delete_finished: bool = False,
            **options,
        ):
        self.name = name
        self.delete_finished = delete_finished
        self.database = self.db_class(database, **options)
        for model in self.models:
            model.bind(self.database)

    def check_conn(self):
        if not self.database.is_connection_usable():
            self.database.close()
            self.database.connect()

    def create_tables(self):
        self.check_conn()
        with self.database.atomic():
            self.database.create_tables(self.models, safe=True)

    def close(self):
        self.database.close()

    def tasks(self, *columns):
        return (
            QueueTask.select(*columns)
            .where(QueueTask.queue == self.name)  # type: ignore
        )

    def schedule(self, *columns):
        return (
            QueueSchedule.select(*columns)
            .where(QueueSchedule.queue == self.name)  # type: ignore
        )

    def kv(self, *columns):
        return (
            QueueKV.select(*columns)
            .where(QueueKV.queue == self.name)  # type: ignore
        )

    def enqueue(self, task, data):  # type: ignore
        self.check_conn()
        QueueTask.create(
            queue=self.name,
            uuid=task.id,
            data=data,
            priority=task.priority or 0,
        )

    def dequeue(self, callback: t.Callable | None = None):
        self.check_conn()
        query = (
            self.tasks(QueueTask.id, QueueTask.data)  # type: ignore
            .where(not QueueTask.done)  # type: ignore
            .order_by(QueueTask.priority.desc(), QueueTask.id)  # type: ignore
            .limit(1)
        )
        if self.for_update:
            query = query.for_update("FOR UPDATE SKIP LOCKED")

        with self.database.atomic():
            try:
                task = query.get()
            except QueueTask.DoesNotExist:  # type: ignore
                return

            if callback:
                callback(task.data)

            if self.delete_finished:
                (
                    QueueTask.delete()
                    .where(QueueTask.id == task.id)  # type: ignore
                    .execute()
                )
            else:
                task.done = True
                task.save()

    def queue_size(self):
        self.check_conn()
        return self.tasks().count()

    def enqueued_items(self, limit=None):
        self.check_conn()
        query = (
            self.tasks(QueueTask.data)  # type: ignore
            .where(not QueueTask.done)  # type: ignore
            .order_by(QueueTask.priority.desc(), QueueTask.id)  # type: ignore
        )
        if limit is not None:
            query = query.limit(limit)
        return list(map(operator.itemgetter(0), query.tuples()))

    def flush_queue(self):
        self.check_conn()
        (
            QueueTask.delete()
            .where(QueueTask.queue == self.name)  # type: ignore
            .execute()
        )

    def add_to_schedule(self, data, ts):
        self.check_conn()
        QueueSchedule.create(queue=self.name, data=data, timestamp=ts)

    def read_schedule(self, ts):
        self.check_conn()
        query = (
            self.schedule(QueueSchedule.id, QueueSchedule.data)  # type: ignore
            .where(QueueSchedule.timestamp <= ts)  # type: ignore
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
                QueueSchedule.delete()
                .where(QueueSchedule.id.in_(id_list))  # type: ignore
                .execute()
            )
            return list(data)

    def schedule_size(self):
        self.check_conn()
        return self.schedule().count()

    def scheduled_items(self, limit: int | None = None):
        self.check_conn()
        tasks = (
            self.schedule(QueueSchedule.data)  # type: ignore
            .order_by(QueueSchedule.timestamp)  # type: ignore
            .limit(limit)
            .tuples()
        )
        return list(map(operator.itemgetter(0), tasks))

    def flush_schedule(self):
        self.check_conn()
        (
            QueueSchedule.delete()
            .where(QueueSchedule.queue == self.name)  # type: ignore
            .execute()
        )

    def put_data(self, key, value, is_result=False):
        self.check_conn()
        QueueKV.replace(queue=self.name, key=key, value=value).execute()

    def peek_data(self, key):
        self.check_conn()
        try:
            kv = (
                self.kv(QueueKV.value)  # type: ignore
                .where(QueueKV.key == key)  # type: ignore
                .get()
            )
        except QueueKV.DoesNotExist:  # type: ignore
            return EmptyData
        else:
            return kv.value

    def pop_data(self, key):
        self.check_conn()
        query = self.kv().where(QueueKV.key == key)  # type: ignore
        if self.for_update:
            query = query.for_update()

        with self.database.atomic():
            try:
                kv = query.get()
            except QueueKV.DoesNotExist:  # type: ignore
                return EmptyData
            else:
                dq = (
                    QueueKV.delete()
                    .where(
                        (QueueKV.queue == self.name)  # type: ignore
                        & (QueueKV.key == key)  # type: ignore
                    )
                )
                return kv.value if dq.execute() == 1 else EmptyData

    def has_data_for_key(self, key):
        self.check_conn()
        return self.kv().where(QueueKV.key == key).exists()  # type: ignore

    def put_if_empty(self, key, value):
        self.check_conn()
        try:
            with self.database.atomic():
                QueueKV.insert(queue=self.name, key=key, value=value).execute()
        except pw.IntegrityError:
            return False
        else:
            return True

    def result_store_size(self):
        self.check_conn()
        return self.kv().count()

    def result_items(self):
        self.check_conn()
        query = self.kv(QueueKV.key, QueueKV.value).tuples()  # type: ignore
        return dict(query.iterator())

    def flush_results(self):
        self.check_conn()
        (
            QueueKV.delete()
            .where(QueueKV.queue == self.name)  # type: ignore
            .execute()
        )


class SqliteStorage(SqlStorage):
    db_class = SqliteExtDatabase
    for_update = False

    def __init__(
        self,
        name: str,
        *,
        database: str,
        delete_finished: bool = False,
        timeout: int = 5,
        **pragmas,
    ):
        # WAL mode allows one or more readers to continue reading
        # while another connection writes to the database.
        pragmas["journal_mode"] = "wal"
        pragmas.setdefault("wal_checkpoint", "full")
        pragmas.setdefault("synchronous", "off")

        self.memory_based = database == ":memory:"
        super().__init__(name, database=database, delete_finished=delete_finished, pragmas=pragmas, timeout=timeout)


class PostgresStorage(SqlStorage):
    db_class = Psycopg3Database
    for_update = True

    def __init__(
        self,
        name: str,
        *,
        database: str,
        delete_finished: bool = False,
        timeout: int = 5,
        psycopg2: bool = False
    ):
        if psycopg2:
            self.db_class = PostgresqlExtDatabase
        super().__init__(name, database=database, delete_finished=delete_finished, timeout=timeout)

    def put_data(self, key, value, is_result=False):
        self.check_conn()
        (
            QueueKV.insert(queue=self.name, key=key, value=value)
            .on_conflict(
                conflict_target=[QueueKV.queue, QueueKV.key],  # type: ignore
                preserve=[QueueKV.value]  # type: ignore
            )
            .execute()
        )
