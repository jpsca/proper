"""Peewee migrations -- 001_base.py.

Create the tables needed for Proper's SQL-based queues.
Delete this file if you are going to use a different queue backend.
"""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    @migrator.create_model
    class QueueKV(pw.Model):
        queue = pw.CharField(max_length=255)
        key = pw.CharField(max_length=255)
        value = pw.BlobField()

        class Meta:
            table_name = "queuekv"
            primary_key = pw.CompositeKey("queue", "key")

    @migrator.create_model
    class QueueSchedule(pw.Model):
        id = pw.AutoField()
        queue = pw.CharField(max_length=255)
        data = pw.BlobField()
        timestamp = pw.TimestampField()

        class Meta:
            table_name = "queueschedule"
            indexes = [(("queue", "timestamp"), False)]

    @migrator.create_model
    class QueueTask(pw.Model):
        id = pw.AutoField()
        queue = pw.CharField(max_length=255)
        uuid = pw.UUIDField(index=True)
        data = pw.BlobField()
        priority = pw.FloatField(default=0.0)
        done = pw.BooleanField(default=False)

        class Meta:
            table_name = "queuetask"
            indexes = [(("done", "priority", "id"), False)]


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model("queuetask")
    migrator.remove_model("queueschedule")
    migrator.remove_model("queuekv")
