from pathlib import Path
from tempfile import mkdtemp
import shutil

from webtest import TestApp
import pytest

from proper import App
from proper.support.secrets import generate_secret_key


SECRET_KEY = generate_secret_key()


@pytest.fixture()
def app():
    app = App(__name__, config={"secret_key": SECRET_KEY, "debug": False})
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
