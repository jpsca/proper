import pytest

from proper import App, g


@pytest.fixture()
def import_name():
    return "tests"


@pytest.fixture()
def app(import_name):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App(import_name, config)
    g.app = app
    return app
