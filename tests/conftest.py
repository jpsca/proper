import pytest

from proper import App, current


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
    current.app = app
    return app
