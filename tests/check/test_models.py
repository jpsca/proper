import peewee as pw
import pytest

from proper.check import ERROR, WARNING, Problem
from proper.check.models import (
    _operations,
    app_models,
    check_migrations,
    check_models,
    check_seeds,
)
from .conftest import FILES, extend


def test_the_models_of_the_app(make_shop):
    app = make_shop()
    assert [model.__name__ for model in app_models(app)] == ["Post"]


def test_an_app_without_models(make_shop):
    app = make_shop({"shop/__init__.py": "from . import main  # noqa\n"}, migrate=False)
    (app.root_path / "models.py").unlink()
    assert app_models(app) == []


def test_models_that_fail_to_import(make_shop):
    app = make_shop({"shop/__init__.py": "from . import main  # noqa\n"}, migrate=False)
    (app.root_path / "models.py").write_text("import not_a_module_anywhere\n")
    with pytest.raises(ModuleNotFoundError):
        app_models(app)


def test_a_field_that_hides_a_method(make_shop):
    app = make_shop(extend("shop/models.py", """

        class Base(pw.Model):
            label = "a value, not a method"

            @property
            def email(self):
                return ""

            def archive(self):
                pass


        class Note(Base):
            body = pw.TextField()
            label = pw.TextField()
            email = pw.TextField()
            archive = pw.BooleanField()
            save = pw.BooleanField()

            class Meta:
                database = app.db["main"]


        class Memo(Note):
            pass
    """))
    problems = check_models(app)
    # Once, where the fields are declared: `Memo` inherits them
    assert [(p.message, p.line) for p in problems] == [
        (
            "the field `Note.archive` hides the method `archive` of Base; rename the "
            'field and keep its column with `column_name="archive"`',
            29,
        ),
        (
            "the field `Note.save` hides the method `save` of Model; rename the "
            'field and keep its column with `column_name="save"`',
            30,
        ),
    ]


def test_two_models_with_one_table(make_shop):
    app = make_shop(extend("shop/models.py", """

        class Article(pw.Model):
            class Meta:
                database = app.db["main"]
                table_name = "posts"
    """), migrate=False)
    [problem] = check_models(app)
    assert problem.message == "Post uses the table `posts` of Article"
    assert (problem.path, problem.line) == ("shop/models.py", 6)


def test_models_that_changed(make_shop):
    app = make_shop()
    app_models(app)[0]._meta.add_field("views", __import__("peewee").IntegerField(default=0))
    [problem] = check_migrations(app)
    assert problem.level == ERROR
    assert problem.path == "db/main"
    assert problem.message.startswith("the models are not what the migrations of `main` make (")
    assert "migrator.add_fields(" in problem.message
    assert problem.message.endswith("): run `proper db create`")


def test_models_without_migrations(make_shop):
    app = make_shop(migrate=False)
    [problem] = check_migrations(app)
    assert problem.message == (
        "the models are not what the migrations of `main` make (create the table "
        "of Post): run `proper db create`"
    )


def test_a_database_without_a_folder(make_shop, tmp_path):
    """`stats` has a model and no migrations; `logs` has neither."""
    files = {
        "shop/main.py": FILES["shop/main.py"].replace(
            '"main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},',
            '"main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},\n'
            '                "stats": {"type": "peewee.SqliteDatabase", "database": "storage/stats.sqlite3"},\n'
            '                "logs": {"type": "peewee.SqliteDatabase", "database": "storage/logs.sqlite3"},',
        ),
        **extend("shop/models.py", """

            class Visit(pw.Model):
                class Meta:
                    database = app.db["stats"]
        """),
    }
    app = make_shop(files)
    [problem] = check_migrations(app)
    assert problem.path == "db/stats"
    assert "(create the table of Visit): run `proper db create --db stats`" in problem.message


def test_files_that_are_not_migrations(make_shop, tmp_path):
    app = make_shop()
    folder = tmp_path / "db" / "main"
    (folder / "__init__.py").write_text("")
    (folder / "notes.txt").write_text("")
    (folder / "add_tags.py").write_text("")
    (folder / "001_other.py").write_text((folder / "001_initial.py").read_text())
    assert check_migrations(app) == [
        Problem(
            WARNING,
            "two migrations are number 001: this one and 001_initial.py (from two "
            "branches?); they run in the order of their names",
            path="db/main/001_other.py",
        ),
        Problem(
            WARNING,
            "this file is not run as a migration: the name of one is three digits, "
            "`_` and a name, like `004_add_tags.py`",
            path="db/main/add_tags.py",
        ),
    ]


def test_a_migration_that_cant_be_read(make_shop, tmp_path):
    app = make_shop()
    (tmp_path / "db" / "main" / "002_broken.py").write_text("def migrate(:\n")
    [problem] = check_migrations(app)
    assert problem.path == "db/main/002_broken.py"
    assert problem.message.startswith("this migration can't be read (SyntaxError: ")
    assert problem.message.endswith(
        "so the models of `main` were not compared with the migrations"
    )


def test_operations():
    code = """
    @migrator.create_model
    class Tag(pw.Model):
        name = pw.TextField()

    migrator.add_fields('posts', views=pw.IntegerField(default=0))
    migrator.add_fields('posts', %s)
    @migrator.create_model
    """ % ", ".join(f"field{n}=pw.IntegerField()" for n in range(9))
    operations = _operations(code)
    assert operations[0] == "create the table of Tag"
    assert operations[1] == "migrator.add_fields('posts', views=pw.IntegerField(default=0))"
    assert len(operations[2]) == 100 and operations[2].endswith("...")
    assert operations[3] == "create the table of a model"


SEEDS_INIT = "from . import roles, users, admins  # noqa\n"
SEED = 'envs = ("dev",)\n\n\ndef seed():\n    pass\n'


def test_seeds(make_shop, tmp_path):
    app = make_shop()
    seeds = tmp_path / "db" / "seeds"
    seeds.mkdir()
    (tmp_path / "db" / "__init__.py").write_text("")
    (seeds / "__init__.py").write_text(SEEDS_INIT)
    (seeds / "roles.py").write_text(SEED)
    (seeds / "users.py").write_text("def seed():\n    pass\n")
    (seeds / "admins.py").write_text('envs = "production"\n')
    (seeds / "forgotten.py").write_text(SEED)
    assert check_seeds(app) == [
        Problem(
            WARNING,
            'this seed has no `envs`, so it never runs; for example: `envs = ("dev",)`',
            path="db/seeds/users.py",
        ),
        Problem(
            WARNING,
            "`envs` is a string, so it runs where APP_ENV is any part of 'production'; "
            "make it a tuple: `envs = ('production',)`",
            path="db/seeds/admins.py",
        ),
        Problem(ERROR, "this seed has no `seed()` function", path="db/seeds/admins.py"),
        Problem(
            WARNING,
            "this seed never runs: `db/seeds/__init__.py` doesn't import it",
            path="db/seeds/forgotten.py",
        ),
    ]


def test_seeds_that_cant_be_imported(make_shop, tmp_path):
    app = make_shop()
    seeds = tmp_path / "db" / "seeds"
    seeds.mkdir()
    (tmp_path / "db" / "__init__.py").write_text("")
    (seeds / "__init__.py").write_text("from . import missing  # noqa\n")
    [problem] = check_seeds(app)
    assert problem.path == "db/seeds/__init__.py"
    assert problem.message.startswith("the seeds can't be imported (ImportError: ")


def test_foreign_keys(make_shop, request):
    files = {
        "shop/main.py": FILES["shop/main.py"].replace(
            '"main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},',
            '"main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},\n'
            '                "stats": {"type": "peewee.SqliteDatabase", "database": "storage/stats.sqlite3"},',
        ),
        "shop/extra.py": """
            import peewee as pw

            from .main import app


            class Tag(pw.Model):
                class Meta:
                    database = app.db["main"]
        """,
        **extend("shop/models.py", """
            from . import extra


            class Visit(pw.Model):
                class Meta:
                    database = app.db["stats"]


            class Comment(pw.Model):
                post = pw.ForeignKeyField(Post)
                parent = pw.ForeignKeyField("self", null=True)
                tag = pw.ForeignKeyField(extra.Tag)
                visit = pw.ForeignKeyField(Visit)
                author = pw.DeferredForeignKey("CheckGhostAuthor")

                class Meta:
                    database = app.db["main"]
        """),
    }
    app = make_shop(files, migrate=False)
    author = app_models(app)[0]._meta.fields["author"]
    request.addfinalizer(lambda: pw.DeferredForeignKey._unresolved.discard(author))
    assert [(p.message, p.line) for p in check_models(app)] == [
        (
            "`Comment.tag` points to Tag, which `models/__init__.py` doesn't import: "
            "the migrations don't make its table",
            24,
        ),
        (
            "`Comment.visit` points to Visit, of another database (`stats`, not "
            "`main`): it can't be joined, nor the key enforced",
            25,
        ),
        (
            "`Comment.author` is a `DeferredForeignKey` to `checkghostauthor`, "
            "and no model of that name was declared",
            26,
        ),
    ]
