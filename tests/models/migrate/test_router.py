"""Tests for the router of `proper.models.migrate`."""

import peewee as pw
import pytest
from playhouse.postgres_ext import ArrayField, TSVectorField
from playhouse.test_utils import count_queries

from proper.models.migrate import Router
from proper.models.migrate.models import MigrateHistory
from proper.models.migrate.router import load_models
from .test_autodiscover.models1 import one_models


def test_router(make_router, migrations):
    class Dummy(pw.Model):
        id = pw.AutoField()

    router = make_router(migrations)

    assert router.database
    assert isinstance(router.database, pw.Database)

    assert router.todo == ["001_test", "002_test", "003_tespy"]
    assert router.done == []
    assert router.diff == ["001_test", "002_test", "003_tespy"]

    router.create("new")
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_new"]
    (migrations / "004_new.py").unlink()

    router.create("new1", auto=Dummy)
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_new1"]
    (migrations / "004_new1.py").unlink()

    router.create("new2", auto=[Dummy])
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_new2"]
    (migrations / "004_new2.py").unlink()

    router.create("new3", auto=f"{__package__}.models")
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_new3"]
    (migrations / "004_new3.py").unlink()

    router.create("new4", auto=[f"{__package__}.models"])
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_new4"]
    (migrations / "004_new4.py").unlink()

    MigrateHistory.create(name="001_test")
    assert router.diff == ["002_test", "003_tespy"]

    MigrateHistory.delete().execute()

    router.run()
    assert router.diff == []

    with count_queries() as counter:
        router.run_one("002_test", router.migrator, fake=True)

    assert not counter.get_queries()

    migrations_done = MigrateHistory.select()
    assert list(migrations_done)
    assert migrations_done.count() == 3

    router.rollback()
    assert router.diff == ["003_tespy"]
    assert migrations_done.count() == 2

    router.merge()
    assert router.todo == ["001_initial"]
    assert MigrateHistory.select().count() == 1

    models = load_models(f"{__package__}.test_autodiscover")
    assert models

    models = load_models(f"{__package__}.test_autodiscover")
    assert models

    models = load_models(one_models)
    assert models

    models = load_models(one_models)
    assert models


def test_router_compile(make_router, tmp_path):
    router = make_router(tmp_path)
    router.compile("test_router_compile")

    assert (tmp_path / "001_test_router_compile.py").read_text()


def test_run_one_error_propagates(make_router, tmp_path):
    (tmp_path / "001_boom.py").write_text(
        "def migrate(migrator, database, **kwargs):\n"
        "    raise RuntimeError('boom')\n"
        "\n"
        "def rollback(migrator, database, **kwargs):\n"
        "    pass\n"
    )
    router = make_router(tmp_path)

    with pytest.raises(RuntimeError, match="boom"):
        router.run()


def _blog_models(db, version):
    class Base(pw.Model):
        class Meta:
            database = db

    class Author(Base):
        name = pw.CharField()

    if version == 1:

        class Post(Base):
            title = pw.CharField(max_length=100, unique=True)
            data = pw.JSONField(null=True)
            author = pw.ForeignKeyField(Author, backref="posts", on_delete="CASCADE")
            price = pw.DecimalField(default=0)
            created = pw.DateTimeField(null=True, index=True)

            class Meta:
                indexes = ((("title", "created"), False),)

    else:

        class Post(Base):
            title = pw.CharField(max_length=200)
            author = pw.ForeignKeyField(Author, backref="posts", on_delete="CASCADE")
            price = pw.DecimalField(default=0, null=True)
            created = pw.DateTimeField(null=True)
            slug = pw.CharField(default="", index=True)
            extra = pw.JSONField(null=True)

    return [Author, Post]


def _schema(database):
    columns = [column.name for column in database.get_columns("post")]
    indexes = sorted((index.name, index.unique) for index in database.get_indexes("post"))
    return columns, indexes


def test_created_migrations_run(make_database, tmp_path):
    """The migrations made from the models run, and so do their rollbacks."""
    database = make_database()

    router = Router(database, migrate_dir=tmp_path)
    assert router.create("first", auto=_blog_models(database, 1)) == "001_first"
    assert Router(database, migrate_dir=tmp_path).run() == ["001_first"]
    first = (
        ["id", "title", "data", "author_id", "price", "created"],
        [
            ("post_author_id", False),
            ("post_created", False),
            ("post_title", True),
            ("post_title_created", False),
        ],
    )
    assert _schema(database) == first

    router = Router(database, migrate_dir=tmp_path)
    assert router.create("second", auto=_blog_models(database, 2)) == "002_second"
    assert Router(database, migrate_dir=tmp_path).run() == ["002_second"]
    assert _schema(database) == (
        ["id", "title", "author_id", "price", "created", "slug", "extra"],
        [("post_author_id", False), ("post_slug", False)],
    )

    router = Router(database, migrate_dir=tmp_path)
    assert router.create("third", auto=_blog_models(database, 2)) is None

    Router(database, migrate_dir=tmp_path).rollback()
    columns, indexes = _schema(database)
    assert sorted(columns) == sorted(first[0])
    assert indexes == first[1]


def test_compile_imports_what_the_code_uses(make_router, tmp_path):
    class Doc(pw.Model):
        title = pw.CharField()
        price = pw.DecimalField(default=0)
        tags = ArrayField(pw.CharField)
        search = TSVectorField()

    class Note(pw.Model):
        title = pw.CharField()

    router = make_router(tmp_path)

    router.create("docs", auto=[Doc])
    router.create("notes", auto=[Doc, Note])

    docs = (tmp_path / "001_docs.py").read_text()
    assert "from decimal import Decimal\n" in docs
    assert "import playhouse.postgres_ext as pw_pext\n" in docs
    assert "tags = pw_pext.ArrayField(" in docs
    assert "field_class=pw.CharField" in docs
    notes = (tmp_path / "002_notes.py").read_text()
    assert "Decimal" not in notes
    assert "pw_pext" not in notes
    # The names in the code of the migrations are defined
    router.run_one("001_docs", router.migrator, fake=True)
    router.run_one("002_notes", router.migrator, fake=True)
    assert {model.__name__ for model in router.migrator} == {"Doc", "Note"}


@pytest.mark.parametrize("max_length", [255, 100], ids=["same_field", "changed_field"])
def test_index_of_a_column_declared_in_meta(make_database, tmp_path, max_length):
    """`migrator.add_index()` marks the field as unique, but the model
    doesn't, and that is not a difference between them."""
    db = make_database()

    def models(version):
        class Post(pw.Model):
            title = pw.CharField(max_length=max_length if version == 3 else 255)

            class Meta:
                database = db
                indexes = ((("title",), True),) if version > 1 else ()

        return [Post]

    for version in (1, 2, 3):
        Router(db, migrate_dir=tmp_path).create("auto", auto=models(version))
        Router(db, migrate_dir=tmp_path).run()

    indexes = [(index.name, index.unique) for index in db.get_indexes("post")]
    assert indexes == [("post_title", True)]
    router = Router(db, migrate_dir=tmp_path)
    assert len(router.done) == (2 if max_length == 255 else 3)
    assert router.create("auto", auto=models(3)) is None
