import os

import pytest
from proper import TestClient

from [[ app_name ]].main import app
from [[ app_name ]].models import db
from [[ app_name ]].models.base import BaseModel


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def db_setup():
    # better to be safe than sorry
    assert os.getenv("APP_ENV") == "test"
    assert "test" in db.database or "memory" in db.database

    # Hold a connection open on the test thread for the whole session: it keeps
    # a shared-cache in-memory DB alive, and lets a server backend configured
    # with autoconnect=False (e.g. Postgres) run the queries below.
    db.connect(reuse_if_open=True)

    models = BaseModel.__subclasses__()
    db.drop_tables(models)
    db.create_tables(models, safe=True)
    load_fixtures()

    yield

    db.drop_tables(models)
    db.close()
    if os.path.exists(db.database):
        os.remove(db.database)


@pytest.fixture(autouse=True)
def db_reset(db_setup):
    # Roll it back for fast, backend-agnostic isolation.
    with db.atomic() as transaction:
        yield
        transaction.rollback()


def load_fixtures():
    pass


