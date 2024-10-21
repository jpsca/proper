import typing as t

from huey.contrib.sql_huey import SqlStorage as HueySqlStorage
from peewee import (
    BlobField,
    CharField,
    CompositeKey,
    FloatField,
    Model,
    TimestampField,
    UUIDField,
)


class BytesBlobField(BlobField):
    def python_value(self, value):
        return value if isinstance(value, bytes) else bytes(value)


class SqlStorage(HueySqlStorage):
    KV : type[Model]
    Schedule : type[Model]
    Task : type[Model]

    def create_models(self) -> tuple:  # type: ignore
        class Base(Model):
            class Meta:
                database = self.database

        class KV(Base):
            queue = CharField()
            key = CharField()
            value = BytesBlobField()

            class Meta:
                primary_key = CompositeKey("queue", "key")
                table_name = "proper_kv"

        self.KV = KV

        class Schedule(Base):
            queue = CharField()
            data = BytesBlobField()
            timestamp = TimestampField(resolution=1000)

            class Meta:
                table_name = "proper_schedule"

        Schedule.add_index(Schedule.queue, Schedule.timestamp, unique=False)
        self.Schedule = Schedule

        class Task(Base):
            queue = CharField()
            uuid = UUIDField(index=True)
            data = BytesBlobField()
            priority = FloatField(default=0.0)

            class Meta:
                table_name = "proper_task"

        Task.add_index(Task.priority.desc(), Task.id)
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
            self.tasks(self.Task.id, self.Task.data)
            .order_by(self.Task.priority.desc(), self.Task.id)
            .limit(1)
        )
        if self.database.for_update:
            query = query.for_update("FOR UPDATE SKIP LOCKED")

        with self.database.atomic():
            try:
                task = query.get()
            except self.Task.DoesNotExist:
                return

            callback(task.data)
            self.Task.delete().where(self.Task.id == task.id).execute()
