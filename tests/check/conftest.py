"""A small app on disk, `shop`, for `proper check`: a test changes or adds
files with `make_shop(files)` before the app is imported."""
import gc
import sys
import textwrap

import pytest

from proper import current
from proper.cli.db_cli import get_db_cli


FILES = {
    "shop/__init__.py": """
        from . import main, router, controllers, models, forms, emails  # noqa
    """,
    "shop/main.py": """
        from proper import App

        CONFIG = {
            "SECRET_KEYS": ["*" * 50],
            "DEBUG": False,
            "DATABASES": {
                "main": {"type": "peewee.SqliteDatabase", "database": "storage/main.sqlite3"},
            },
        }
        app = App(__name__, CONFIG)
    """,
    "shop/router.py": """
        from .main import app

        router = app.router
    """,
    "shop/controllers.py": """
        from proper import Controller, errors

        from .router import router


        class PostController(Controller):
            @router.get("posts")
            def index(self):
                pass

            @router.get("posts/{id}")
            def show(self):
                pass

            @router.error(errors.NotFound)
            def not_found(self):
                pass
    """,
    "shop/models.py": """
        import peewee as pw

        from .main import app


        class Post(pw.Model):
            title = pw.TextField()

            class Meta:
                database = app.db["main"]
                table_name = "posts"
    """,
    "shop/forms.py": """
        import formidable as f

        from .models import Post


        class PostForm(f.Form):
            title = f.TextField()

            class Meta:
                orm_cls = Post
    """,
    "shop/emails/__init__.py": """
        from . import welcome_email  # noqa
    """,
    "shop/emails/welcome_email.py": """
        from proper.emails import EmailMessage


        class WelcomeEmail(EmailMessage):
            subject = "Welcome"
    """,
    "shop/views/emails/welcome.jx": """
        <p>Welcome</p>
    """,
    "shop/views/post/index.jx": """
        <h1>Posts</h1>
    """,
}


def extend(name, code):
    """The file `name` of the app with `code` added at the end."""
    return {name: textwrap.dedent(FILES[name]) + textwrap.dedent(code)}


def write(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip())


def forget_modules():
    """Drop the modules of the last app, and its classes: the checks find
    forms and emails among the subclasses of their base."""
    for key in list(sys.modules):
        if key.split(".")[0] in ("shop", "db"):
            sys.modules.pop(key, None)
    gc.collect()


@pytest.fixture()
def make_shop(tmp_path, monkeypatch):
    """Write the `shop` app with `files` changed or added, import it, and
    give it a migration made from its models (unless `migrate=False`)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "storage").mkdir()
    (tmp_path / "db" / "main").mkdir(parents=True)
    apps = []

    def make_shop(files=None, *, migrate=True):
        forget_modules()
        write(tmp_path, {**FILES, **(files or {})})
        __import__("shop")
        app = sys.modules["shop.main"].app
        apps.append(app)
        if migrate:
            get_db_cli(app)().create(name="initial")
        return app

    yield make_shop
    forget_modules()
    current.app = None
    for app in apps:
        for db in app.db.values():
            db.close()
