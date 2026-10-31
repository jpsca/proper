import json
from datetime import date, datetime

import peewee as pw
import pytest

from proper import JSONField
from proper.helpers import jsonplus


@pytest.fixture()
def db():
    db = pw.SqliteDatabase(":memory:")
    yield db
    db.close()


def test_is_a_peewee_json_field(db):
    class Note(pw.Model):
        data = JSONField(null=True)

        class Meta:
            database = db

    assert isinstance(Note.data, pw.JSONField)
    db.create_tables([Note])
    note = Note.create(data={"tags": ["a", "b"], "n": 1})
    assert Note.get_by_id(note.id).data == {"tags": ["a", "b"], "n": 1}
    assert Note.create(data=None).data is None


def test_dates_round_trip_as_before(db):
    """The data an app stored with the old field keeps loading the same."""

    class Note(pw.Model):
        data = JSONField()

        class Meta:
            database = db

    db.create_tables([Note])
    when = datetime(2024, 1, 2, 3, 4, 5)
    note = Note.create(data={"day": date(2024, 1, 2), "when": when})

    raw = db.execute_sql("select data from note").fetchone()[0]
    # The same encoding the old field wrote (SQLite normalizes the spacing)
    assert json.loads(raw) == json.loads(jsonplus.dumps({"day": date(2024, 1, 2), "when": when}))
    assert "__dt__2024-01-02" in raw

    loaded = Note.get_by_id(note.id).data
    assert loaded == {"day": date(2024, 1, 2), "when": when}


def test_json_path_queries_work(db):
    class Note(pw.Model):
        data = JSONField()

        class Meta:
            database = db

    db.create_tables([Note])
    Note.create(data={"kind": "a"})
    Note.create(data={"kind": "b"})
    assert Note.select().where(Note.data["kind"] == "a").count() == 1


def test_custom_encoders_can_be_given(db):
    class Note(pw.Model):
        data = JSONField(dumps=json.dumps, loads=json.loads)

        class Meta:
            database = db

    db.create_tables([Note])
    with pytest.raises(TypeError):
        Note.create(data={"day": date(2024, 1, 2)})
