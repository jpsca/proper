"""The `CABLE` config: which backend an app gets."""
import pytest

from proper import App, current
from proper.channels import BaseCable, Cable
from proper.errors import ConfigError
from proper.tools.cable import validate_config


SECRET = "*" * 50


def _app(**config):
    app = App("proper", {"SECRET_KEYS": [SECRET], **config})
    current.app = app
    return app


class TestCableTool:
    def test_no_config_creates_a_cable_without_websockets(self):
        cable = _app().cable
        assert type(cable) is BaseCable
        assert not getattr(cable, "serves_websockets", False)

    def test_an_empty_dict_creates_a_cable_without_websockets(self):
        assert type(_app(CABLE={}).cable) is BaseCable

    def test_a_cable_port_without_a_cable_is_refused(self):
        with pytest.raises(ConfigError, match="Cable"):
            _app(CABLE={}, CABLE_PORT=2301)

    def test_a_class_path(self):
        cable = _app(CABLE={"type": "proper.channels.Cable"}).cable
        assert type(cable) is Cable

    def test_a_class_and_its_options(self):
        cable = _app(CABLE={"type": Cable, "workers": 2, "host": "127.0.0.1"}).cable
        assert type(cable) is Cable
        assert (cable._workers, cable._host) == (2, "127.0.0.1")


class TestCableToolValidation:
    def test_rejects_non_dict(self):
        with pytest.raises(ConfigError, match="must be a dictionary"):
            validate_config("bad")

    def test_rejects_missing_type(self):
        with pytest.raises(ConfigError, match="must have a 'type' key"):
            validate_config({"url": "redis://localhost"})

    def test_rejects_bad_type_value(self):
        with pytest.raises(ConfigError, match="must be a string or a class"):
            validate_config({"type": 42})

    def test_accepts_valid_config(self):
        validate_config({"type": "proper.channels.Cable"})
        validate_config({"type": Cable})
