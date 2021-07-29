import shutil
from pathlib import Path
from tempfile import mkdtemp

import pytest
from webtest import TestApp

from proper import App, BaseController, errors


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
SCAF_CONTROLLER = """from proper import BaseController

class Pages(BaseController):
    def index(self):
        pass
"""
SCAFF_ROUTES = """
routes = [
    get("", to=Pages.index),
]

"""


@pytest.fixture()
def scaffold(dst):
    app_root = Path(dst) / APP_NAME
    (app_root / "controllers").mkdir(parents=True, exist_ok=True)
    (app_root / "templates").mkdir(parents=True, exist_ok=True)
    (app_root / "controllers" / "__init__.py").touch()
    (app_root / "controllers" / "pages.py").write_text(SCAF_CONTROLLER)
    (app_root / "routes.py").write_text(SCAFF_ROUTES)
    return app_root


class AppController(BaseController):
    def _render(self):
        return f"<html>{self.resp.template} was rendered</html>"


class _Pages(AppController):
    def index(self, *args):
        self.resp.body = "Hello World!"
        self.resp.content_type = "text/plain"
        assert self.resp.content_type == "text/plain"

    def echo(self, *args):
        self.resp.raw_body = self.req.stream

    def rendered(self, *args):
        pass

    def fail_not_acceptable(self):
        raise errors.NotAcceptable("Do it again!")

    def fail_not_implemented(self):
        raise errors.NotImplemented("It will be ready when it will be ready")

    def fail_forbidden(self):
        raise errors.Forbidden("Go away!")

    def fail_value_error(self):
        raise ValueError("A non-http exception")

    def custom_not_found_handler(self):
        self.resp.body = "Custom not found handler"

    def custom_not_acceptable_handler(self):
        self.resp.body = "Custom not acceptable handler"

    def custom_error_handler(self):
        self.resp.body = "Custom error handler"

    def custom_value_error_handler(self):
        self.resp.body = "Custom value error handler"

    def append(self):
        self.resp.body = (self.resp.body or "") + "-index-"

    def set_template(self):
        self.resp.template = "from_controller.jinja"

    def json(self):
        self.resp.body = {"Hello": "World"}

    def charset(self):
        self.resp.charset = "latin1"
        self.resp.body = "Hello World!"

    def bytes(self):
        self.resp.body = b"bytes"


@pytest.fixture(scope="session")
def Pages():
    return _Pages
