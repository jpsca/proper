import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest
from webtest import TestApp

from proper import App
from proper.cli import secret


SECRET_KEY = secret()


@pytest.fixture()
def import_name():
    return "tests"


@pytest.fixture()
def app(import_name):
    app = App(import_name, config={"secret_key": SECRET_KEY})
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
