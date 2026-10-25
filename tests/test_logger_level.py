"""The framework logger writes from `LOG_LEVEL`."""
import logging

import pytest

from proper import App
from proper.errors import ConfigError
from proper.helpers import logger


def make_app(**config):
    return App("proper", {"SECRET_KEYS": ["*" * 50], **config})


def test_debug_logs_everything():
    app = make_app(LOG_LEVEL="debug")
    assert app.config.LOG_LEVEL == "debug"
    assert logger.level == logging.DEBUG
    assert logger.isEnabledFor(logging.DEBUG)


def test_otherwise_debug_messages_are_not_even_built():
    make_app(LOG_LEVEL="info")
    assert logger.level == logging.INFO
    assert not logger.isEnabledFor(logging.DEBUG)
    assert logger.isEnabledFor(logging.INFO)


def test_an_unknown_level_is_an_error():
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        make_app(LOG_LEVEL="verbose")
