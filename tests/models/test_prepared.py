"""Prepared queries (`proper.db.prepared`) on the released Peewee."""
import datetime

import peewee as pw
import pytest

from proper.db import Param, PreparedQuery, prepare


class CountingDatabase(pw.SqliteDatabase):
    """Counts the SQL statements it runs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queries = 0

    def execute_sql(self, sql, params=None, *args, **kwargs):
        self.queries += 1
        return super().execute_sql(sql, params, *args, **kwargs)


database = CountingDatabase(":memory:")


class Person(pw.Model):
    first = pw.CharField()
    last = pw.CharField()
    dob = pw.DateField(null=True)

    class Meta:
        database = database


class Note(pw.Model):
    author = pw.ForeignKeyField(Person)
    content = pw.TextField()

    class Meta:
        database = database


@pytest.fixture()
def people():
    database.connect(reuse_if_open=True)
    database.create_tables([Person, Note])
    huey = Person.create(first="huey", last="cat", dob=datetime.date(2010, 1, 2))
    zaizee = Person.create(first="zaizee", last="cat", dob=datetime.date(2012, 3, 4))
    for i in range(5):
        Note.create(author=huey if i % 2 else zaizee, content=f"note-{i}")
    yield huey, zaizee
    database.drop_tables([Person, Note])
    database.close()


def test_same_results_as_the_query(people):
    prepared = prepare(Note.select().where(Note.author == Param("author")).order_by(Note.id))
    assert isinstance(prepared, PreparedQuery)
    for person in people:
        expected = [n.content for n in Note.select().where(Note.author == person).order_by(Note.id)]
        for _ in range(2):  # compiled once, executed twice
            assert [n.content for n in prepared.execute(author=person)] == expected


def test_values_are_converted_by_the_field(people):
    huey, _ = people
    # A date for a date field, a model instance or its id for a foreign key.
    since = prepare(Person.select().where(Person.dob > Param("since")))
    assert [p.first for p in since.execute(since=datetime.date(2011, 1, 1))] == ["zaizee"]
    by_author = prepare(Note.select().where(Note.author == Param("a")))
    assert len(list(by_author.execute(a=huey))) == len(list(by_author.execute(a=huey.id))) == 2


def test_joins_row_types_and_limit(people):
    prepared = prepare(
        Note.select(Note, Person)
        .join(Person)
        .where(Person.last == Param("last"))
        .order_by(Note.id.desc())
        .limit(Param("n"))
    )
    notes = list(prepared.execute(last="cat", n=2))
    assert [n.content for n in notes] == ["note-4", "note-3"]
    assert notes[0].author.first == "zaizee"
    before = database.queries
    assert notes[1].author.first == "huey"  # joined: no query to load it
    assert database.queries == before

    dicts = prepare(Person.select().where(Person.first == Param("f")).dicts())
    assert dicts.first(f="huey")["last"] == "cat"
    assert dicts.first(f="nobody") is None
    tuples = prepare(
        Person.select(Person.first).where(Person.last == Param("l")).order_by(Person.first).tuples()
    )
    assert list(tuples.execute(l="cat")) == [("huey",), ("zaizee",)]


def test_a_param_used_twice(people):
    prepared = prepare(
        Person.select()
        .where((Person.first == Param("name")) | (Person.last == Param("name")))
        .order_by(Person.first)
    )
    assert [p.first for p in prepared.execute(name="cat")] == ["huey", "zaizee"]
    assert [p.first for p in prepared.execute(name="huey")] == ["huey"]


def test_subquery_with_params(people):
    authors = Person.select(Person.id).where(Person.first == Param("first"))
    prepared = prepare(Note.select().where(Note.author.in_(authors)).order_by(Note.id))
    assert [n.content for n in prepared.execute(first="huey")] == ["note-1", "note-3"]


def test_writes(people):
    huey, _ = people
    update = prepare(Person.update(last=Param("last")).where(Person.first == Param("first")))
    assert update.execute(first="huey", last="kitty") == 1
    assert Person.get(Person.first == "huey").last == "kitty"
    delete = prepare(Note.delete().where(Note.author == Param("author")))
    assert delete.execute(author=huey) == 2
    assert Note.select().count() == 3


def test_sql_shows_the_params(people):
    prepared = prepare(Person.select().where(Person.first == Param("f")))
    sql, params = prepared.sql()
    assert sql.endswith('WHERE ("t1"."first" = ?)')
    assert repr(params) == "[Param('f')]"
    assert repr(prepared).startswith("<PreparedQuery ")


def test_values_that_would_change_the_sql_are_refused(people):
    prepared = prepare(Person.select().where(Person.id.in_(Param("ids"))))
    with pytest.raises(ValueError, match="would change the SQL"):
        list(prepared.execute(ids=[1, 2]))
    prepared = prepare(Person.select().where(Person.first == Param("f")))
    with pytest.raises(ValueError, match="would change the SQL"):
        list(prepared.execute(f=Person.last))
    # Not an expression itself, but it would compile to one: a model class.
    prepared = prepare(Person.select().limit(Param("n")))
    with pytest.raises(ValueError, match="would change the SQL"):
        list(prepared.execute(n=Person))


def test_missing_and_unknown_values(people):
    prepared = prepare(Person.select().where(Person.first == Param("f")))
    with pytest.raises(ValueError, match=r"missing \['f'\]"):
        prepared.execute()
    with pytest.raises(ValueError, match=r"unknown \['g'\]"):
        prepared.execute(f="huey", g="x")


def test_returning_is_not_supported(people):
    with pytest.raises(ValueError, match="RETURNING"):
        prepare(Person.insert(first="a", last="b").returning(Person.id))


def test_recompiled_for_another_database(people):
    prepared = prepare(Person.select().where(Person.first == Param("f")))
    assert prepared.first(f="huey").last == "cat"
    other = pw.SqliteDatabase(":memory:")
    with other.bind_ctx([Person]):
        other.create_tables([Person])
        Person.create(first="huey", last="other")
        assert prepared.first(other, f="huey").last == "other"
    assert prepared.first(f="huey").last == "cat"


def test_a_query_through_a_proxy(people):
    proxy = pw.DatabaseProxy()
    proxy.initialize(database)

    class Proxied(pw.Model):
        first = pw.CharField()

        class Meta:
            database = proxy
            table_name = "person"

    prepared = prepare(Proxied.select().where(Proxied.first == Param("f")))
    assert prepared.first(f="zaizee").first == "zaizee"


def test_an_unbound_query_is_refused():
    class Loose(pw.Model):
        name = pw.CharField()

    prepared = prepare(Loose.select().where(Loose.name == Param("n")))
    with pytest.raises(pw.InterfaceError, match="bound to a database"):
        prepared.execute(n="x")
