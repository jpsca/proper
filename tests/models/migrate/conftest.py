import shutil
from pathlib import Path

import psycopg
import pymysql
import pytest
from peewee import (
    CharField,
    ForeignKeyField,
    IntegerField,
    Model,
    MySQLDatabase,
    PostgresqlDatabase,
)
from playhouse.db_url import connect

from proper.models.migrate import Migrator, Router
from .mocks import mysql, postgres


MIGRATIONS = Path(__file__).parent / "migrations"


@pytest.fixture
def dburl():
    return "sqlite:///:memory:"


@pytest.fixture
def make_database(monkeypatch):
    """Makes the database of a URL. One of Postgres uses `psycopg` and one
    of MySQL uses `pymysql`, with a connection that only records its
    queries: there is no server."""
    databases = []
    monkeypatch.setattr(psycopg, "connect", postgres.RecordingConnection)
    monkeypatch.setattr(pymysql, "connect", mysql.RecordingConnection)

    def make_database(dburl="sqlite:///:memory:"):
        if dburl.startswith("postgres"):
            database = PostgresqlDatabase("fake", prefer_psycopg3=True)
        elif dburl.startswith("mysql"):
            database = MySQLDatabase("fake")
        else:
            database = connect(dburl)
        databases.append(database)
        return database

    yield make_database
    for database in databases:
        database.close()


@pytest.fixture
def database(make_database, dburl):
    return make_database(dburl)


@pytest.fixture
def make_router(make_database):
    def make_router(migrate_dir, dburl="sqlite:///:memory:"):
        return Router(make_database(dburl), migrate_dir=migrate_dir)

    return make_router


@pytest.fixture
def router(database, tmp_path):
    return Router(database, migrate_dir=tmp_path / "migrations")


@pytest.fixture
def migrations(tmp_path):
    """A copy of the folder of migrations, for a test to write in."""
    return Path(shutil.copytree(MIGRATIONS, tmp_path / "migrations"))


@pytest.fixture
def models():
    class Customer(Model):
        name = CharField()
        age = IntegerField()

    class Order(Model):
        number = CharField()
        uid = CharField(unique=True)

        customer = ForeignKeyField(Customer, column_name="customer_id")

    return [Customer, Order]


@pytest.fixture
def migrator(database, models):
    Customer, Order = models
    migrator = Migrator(database)
    migrator.create_model(Customer)
    migrator.create_model(Order)
    migrator()
    return migrator
