import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest
from webtest import TestApp

from proper import App


@pytest.fixture()
def import_name():
    return "tests"


@pytest.fixture()
def app(import_name):
    app = App(import_name, config={"secret_key": "*" * 50, "debug": False})
    return app


@pytest.fixture()
def web(app):
    return TestApp(app)


@pytest.fixture()
def dst(request):
    """Return a real temporary folder path which is unique to each test
    function invocation. This folder is deleted after the test has finished.
    """
    dst = mkdtemp()
    request.addfinalizer(lambda: shutil.rmtree(dst))
    return Path(dst)


@pytest.fixture()
def assets_path():
    return Path(__file__).parent / "assets"


APP_NAME = "app"


@pytest.fixture()
def scaffold(dst):
    app_root = Path(dst) / APP_NAME
    (app_root / "controllers").mkdir(parents=True, exist_ok=True)
    (app_root / "templates").mkdir(parents=True, exist_ok=True)
    (app_root / "controllers" / "__init__.py").touch()
    (app_root / "routes.py").write_text("""routes = [
    get("", to="Pages.index"),
]

""")
    return app_root
