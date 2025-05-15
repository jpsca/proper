"""Peewee migrations -- 001_base.py.

Create the tables needed for Proper's database-based cache.
Delete this file if you are going to use a different cache backend.
"""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    @migrator.create_model
    class Cache(pw.Model):
        key = pw.TextField(primary_key=True)
        value = pw.BlobField()
        timestamp = pw.IntegerField(index=True)

        class Meta:
            table_name = "proper_cache"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.remove_model("proper_cache")
