import sys
import types

import peewee as pw
import pytest

from proper import App
from proper.cli.db_cli import get_db_cli


MIGRATION = """\
import peewee as pw


def migrate(migrator, database, *, fake=False):
    @migrator.create_model
    class {model}(pw.Model):
        name = pw.TextField()

        class Meta:
            table_name = "{table}"


def rollback(migrator, database, *, fake=False):
    migrator.remove_model("{table}")
"""

SEED = """\
envs = ("dev",)


def seed():
    from pathlib import Path

    Path("seeded.txt").write_text("yes")
"""


@pytest.fixture(autouse=True)
def _isolate_db_modules():
    """Clear the cached `db.*` modules, because each test makes its own
    `db/seeds/` package."""
    yield
    for key in list(sys.modules):
        if key == "db" or key.startswith("db."):
            sys.modules.pop(key, None)


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """A project root with a migration for each of its two databases
    and a seed for the main one."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "storage").mkdir()

    for db, model, table in (("main", "Post", "posts"), ("stats", "Visit", "visits")):
        folder = tmp_path / "db" / db
        folder.mkdir(parents=True)
        (folder / "001_initial.py").write_text(MIGRATION.format(model=model, table=table))

    seeds = tmp_path / "db" / "seeds"
    seeds.mkdir()
    (tmp_path / "db" / "__init__.py").write_text("")
    (seeds / "__init__.py").write_text("from . import first  # noqa\n")
    (seeds / "first.py").write_text(SEED)
    return tmp_path


@pytest.fixture()
def make_app(project):
    apps = []

    def make_app(env="dev", **config):
        app = App(
            __name__,
            {
                "SECRET_KEYS": ["*" * 50],
                "DEBUG": False,
                "DATABASES": {
                    "main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},
                    "stats": {"type": "peewee.SqliteDatabase", "database": "storage/stats.sqlite3"},
                },
                **config,
            },
        )
        app.env = env
        apps.append(app)
        return app

    yield make_app
    for app in apps:
        for db in app.db.values():
            db.close()


@pytest.fixture()
def app(make_app):
    return make_app()


def test_prepare_migrates_every_database(project, app, capsys):
    get_db_cli(app)().prepare()

    assert app.db["main"].table_exists("posts")
    assert app.db["stats"].table_exists("visits")
    out = capsys.readouterr().out
    assert "db/main/001_initial.py" in out
    assert "db/stats/001_initial.py" in out


def test_prepare_seeds_the_main_database(project, app, capsys):
    get_db_cli(app)().prepare()

    assert (project / "seeded.txt").read_text() == "yes"
    assert "db/seeds/first.py - ran" in capsys.readouterr().out


def test_prepare_one_database(project, app):
    get_db_cli(app)().prepare(db="stats")

    assert app.db["stats"].table_exists("visits")
    assert not app.db["main"].table_exists("posts")
    # The seed is of the main database
    assert not (project / "seeded.txt").exists()


def test_prepare_does_not_seed_in_tests(project, make_app):
    app = make_app(env="test")
    get_db_cli(app)().prepare()

    assert app.db["main"].table_exists("posts")
    assert not (project / "seeded.txt").exists()


def test_prepare_twice(project, app, capsys):
    cli = get_db_cli(app)()
    cli.prepare()
    capsys.readouterr()

    cli.prepare()

    assert "No pending migrations found." in capsys.readouterr().out


def test_prepare_with_a_cache_in_a_file(project, make_app):
    """The cache makes its own table: it works before `db prepare`,
    and `db prepare` has nothing to do for it."""
    app = make_app(
        CACHE={"type": "proper.cache.SqliteCache", "database": "storage/cache.sqlite3"}
    )
    app.cache.set("a", 1)

    get_db_cli(app)().prepare()

    assert app.cache.get("a") == 1
    assert app.db["main"].table_exists("posts")


def test_migration_of_the_cache_made_by_the_app(project, make_app, capsys):
    """An app that already has a migration for the table of the cache
    can still run it, before or after the cache made the table."""
    app = make_app(
        CACHE={"type": "proper.cache.SqliteCache", "database": "storage/cache.sqlite3"}
    )
    cli = get_db_cli(app)()
    app.cache.set("a", 1)

    cli.create(name="cache", db="proper_cache")
    cli.prepare()

    out = capsys.readouterr().out
    assert "Running migrations for 'proper_cache':" in out
    assert app.cache.get("a") == 1


def test_create_takes_the_models_of_that_database(project, app, monkeypatch, capsys):
    """A migration for one database has only the models stored in it."""
    models = types.ModuleType("blog.models")

    class Post(pw.Model):
        title = pw.TextField()

        class Meta:
            database = app.db["main"]
            table_name = "posts"

    class Visit(pw.Model):
        path = pw.TextField()
        count = pw.IntegerField()

        class Meta:
            database = app.db["stats"]
            table_name = "visits"

    models.Post = Post
    models.Visit = Visit
    monkeypatch.setitem(sys.modules, "blog.models", models)
    app.name = "blog"
    cli = get_db_cli(app)()

    cli.create(name="more", db="stats")

    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert out.startswith("db/stats/002_more")
    migration = (project / out).read_text()
    assert "count" in migration
    assert "title" not in migration


def test_create_without_models_for_that_database(project, app, monkeypatch, capsys):
    models = types.ModuleType("blog.models")
    monkeypatch.setitem(sys.modules, "blog.models", models)
    app.name = "blog"
    cli = get_db_cli(app)()

    with pytest.raises(SystemExit) as exc:
        cli.create(name="more", db="stats")

    assert exc.value.code == 0
    assert "No models found." in capsys.readouterr().out
    assert sorted(p.name for p in (project / "db" / "stats").iterdir()) == ["001_initial.py"]
