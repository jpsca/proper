import peewee as pw
import pytest

from proper.models import base as models_base
from proper.models import scope


@pytest.fixture(autouse=True)
def fresh_cache():
    models_base._FIND_SQL.clear()
    yield
    models_base._FIND_SQL.clear()


@pytest.fixture()
def Book(db, BaseModel):
    class Book(BaseModel):
        title = pw.CharField()
        pages = pw.IntegerField(default=0)

        @scope
        def long(cls, query):
            return query.where(cls.pages > 300)

    db.create_tables([Book])
    Book.create(title="A", pages=100)
    Book.create(title="B", pages=400)
    return Book


def test_finds_a_row(Book):
    book = Book.find(2)
    assert isinstance(book, Book)
    assert (book.id, book.title, book.pages) == (2, "B", 400)


def test_missing_row_is_none(Book):
    assert Book.find(99) is None


def test_none_is_none(Book):
    assert Book.find(None) is None


def test_scopes_do_not_apply(Book):
    assert Book.find(1).title == "A"


def test_the_row_is_a_clean_instance(Book):
    book = Book.find(1)
    assert book.dirty_fields == []
    book.pages = 150
    book.save()
    assert Book.find(1).pages == 150


def test_the_sql_is_generated_once_per_model_and_database(Book, db, monkeypatch):
    Book.find(1)
    assert list(models_base._FIND_SQL) == [(Book, db)]
    sql = models_base._FIND_SQL[(Book, db)]
    assert sql == Book.select().where(Book.id == 0).sql()[0]

    calls = []
    original = pw.ModelSelect.sql

    def counting(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pw.ModelSelect, "sql", counting)
    assert Book.find(2).title == "B"
    assert Book.find(99) is None
    assert calls == []


def test_another_database_gets_its_own_sql(Book, db):
    Book.find(1)
    other = pw.SqliteDatabase(":memory:")
    Book._meta.database = other
    try:
        other.create_tables([Book])
        assert Book.find(1) is None
        assert set(models_base._FIND_SQL) == {(Book, db), (Book, other)}
    finally:
        Book._meta.database = db


def test_non_integer_primary_key(db, BaseModel):
    class Tag(BaseModel):
        name = pw.CharField(primary_key=True)

    db.create_tables([Tag])
    Tag.create(name="red")
    assert Tag.find("red").name == "red"
    assert Tag.find("blue") is None


def test_a_converted_primary_key(db, BaseModel):
    import uuid

    class Doc(BaseModel):
        key = pw.UUIDField(primary_key=True)

    db.create_tables([Doc])
    key = uuid.uuid4()
    Doc.create(key=key)
    assert Doc.find(key).key == key
    assert Doc.find(str(key)).key == key


def test_a_model_without_primary_key(db, BaseModel):
    class Log(BaseModel):
        line = pw.CharField()

        class Meta:
            primary_key = False

    with pytest.raises(ValueError, match="Log has no primary key"):
        Log.find(1)
