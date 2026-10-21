"""The auth addon's models, as `proper install auth` writes them into an
app, for the tests of this folder."""
import importlib
import sys

import pytest

from proper.auth.install import AUTH_BLUEPRINT
from proper.helpers import render_blueprint


APP_NAME = "ipaddrapp"

BASE_MODEL = """\
import peewee as pw
from proper.models import ProperModel

db = pw.SqliteDatabase(":memory:")


class BaseModel(ProperModel):
    class Meta:
        database = db
"""

@pytest.fixture()
def models(tmp_path, app):
    """The auth addon's models, as `proper install auth` writes them into
    an app, on an in-memory database."""
    root = tmp_path / APP_NAME
    for folder in ("controllers", "cli", "config", "emails", "forms", "models", "views"):
        (root / folder).mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "main.py").write_text(
        'from proper import App\napp = App(__name__, {"SECRET_KEYS": ["*" * 50]})\n'
        # As in a real app: the auth validators import it
        "config = app.config\n"
    )
    for folder in ("cli", "config", "emails", "models"):
        (root / folder / "__init__.py").write_text("")
    (root / "models" / "base.py").write_text(BASE_MODEL)
    (root / "views" / "nav.jx").write_text("<nav></nav>\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "conftest.py").write_text("")
    render_blueprint(AUTH_BLUEPRINT, tmp_path, context={"app_name": APP_NAME})

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module(f"{APP_NAME}.models")
        db = module.base.db
        db.create_tables([module.User, module.Session])
        yield module
        db.close()
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == APP_NAME or name.startswith(f"{APP_NAME}."):
                del sys.modules[name]


@pytest.fixture()
def user(models):
    return models.User.create(login="ada@example.com", password="correct horse battery")
