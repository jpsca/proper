import warnings

import pytest
warnings.filterwarnings("ignore")

from proper import App


@pytest.fixture()
def import_name():
    return "tests"


@pytest.fixture()
def app(import_name):
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App(import_name, config=config)
    return app
