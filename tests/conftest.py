from pathlib import Path

import pytest
from webtest import TestApp

from proper import App, Controller, errors


@pytest.fixture()
def import_name():
    return "tests"


@pytest.fixture()
def app(import_name):
    app = App(import_name, config={"secret_keys": ["*" * 50], "debug": False})
    return app


@pytest.fixture()
def web(app):
    return TestApp(app)


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
def scaffold(tmp_path):
    app_root = Path(tmp_path) / APP_NAME
    (app_root / "controllers").mkdir(parents=True, exist_ok=True)
    (app_root / "components").mkdir(parents=True, exist_ok=True)
    (app_root / "controllers" / "__init__.py").touch()
    (app_root / "controllers" / "pages.py").write_text(SCAF_CONTROLLER)
    (app_root / "routes.py").write_text(SCAFF_ROUTES)
    return app_root


class AppController(Controller):
    def render(self):
        return f"<html>{self.response.component} was rendered</html>"


class _Pages(AppController):
    def index(self, *args):
        self.response.body = "Hello World!"
        self.response.content_type = "text/plain"

    def echo(self, *args):
        self.response.raw_body = self.request.body

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
        self.response.body = "Custom not found handler"

    def custom_not_acceptable_handler(self):
        self.response.body = "Custom not acceptable handler"

    def custom_error_handler(self):
        self.response.body = "Custom error handler"

    def custom_value_error_handler(self):
        self.response.body = "Custom value error handler"

    def append(self):
        self.response.body = (self.response.body or "") + "-index-"

    def set_component(self):
        self.response.component = "FromController"

    def charset(self):
        self.response.charset = "latin1"
        self.response.body = "Hello World!"

    def bytes(self):
        self.response.body = b"bytes"


@pytest.fixture(scope="session")
def Pages():
    return _Pages
