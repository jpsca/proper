import pytest

from app.models import db
from app.models.base import BaseModel


@pytest.fixture(scope="session")
def db_setup():
    # better to be safe than sorry
    assert "_test" in db.database or db.database == ":memory:"
    models = BaseModel.__subclasses__()
    db.drop_tables(models)
    db.create_tables(models, safe=True)
    load_fixtures()
    yield
    db.drop_tables(models)


def load_fixtures():
    pass


@pytest.fixture(autouse=True)
def dbs(db_setup):
    with db.atomic() as transaction:
        yield
        transaction.rollback()


