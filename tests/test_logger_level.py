"""The framework logger follows the app's debug setting."""
import logging

from proper import App
from proper.helpers import logger


def make_app(**config):
    return App("proper", {"SECRET_KEYS": ["*" * 50], **config})


def test_debug_mode_logs_everything():
    make_app(DEBUG=True)
    assert logger.level == logging.DEBUG
    assert logger.isEnabledFor(logging.DEBUG)


def test_otherwise_debug_messages_are_not_even_built():
    make_app(DEBUG=False)
    assert logger.level == logging.INFO
    assert not logger.isEnabledFor(logging.DEBUG)
    assert logger.isEnabledFor(logging.INFO)
