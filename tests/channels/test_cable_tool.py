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


class TestCableSettings:
    """The `CABLE_*` settings are checked when a cable is configured."""

    CABLE = {"type": "proper.channels.Cable"}

    def test_defaults_pass(self):
        _app(CABLE=self.CABLE)

    @pytest.mark.parametrize("value", [0, -1, 2.5, "3", True])
    def test_the_ping_interval_is_a_whole_number_of_seconds(self, value):
        with pytest.raises(ConfigError, match="CABLE_PING_INTERVAL must be an integer of at least 1"):
            _app(CABLE=self.CABLE, CABLE_PING_INTERVAL=value)

    def test_the_pings_come_before_the_idle_timeout(self):
        _app(CABLE={**self.CABLE, "idle_timeout": 10}, CABLE_PING_INTERVAL=3)
        with pytest.raises(ConfigError, match="idle_timeout.*greater than CABLE_PING_INTERVAL"):
            _app(CABLE={**self.CABLE, "idle_timeout": 3}, CABLE_PING_INTERVAL=3)
        with pytest.raises(ConfigError, match="idle_timeout"):
            _app(CABLE={**self.CABLE, "idle_timeout": "60"})

    @pytest.mark.parametrize("option", ["ping_interval", "allowed_origins", "recovery_enabled"])
    def test_options_a_setting_decides_are_refused(self, option):
        with pytest.raises(ConfigError, match=f"CABLE\\['{option}'\\] is set by"):
            _app(CABLE={**self.CABLE, option: 1})

    @pytest.mark.parametrize("value", [-1, 70000, "2301"])
    def test_the_port(self, value):
        with pytest.raises(ConfigError, match="CABLE_PORT"):
            _app(CABLE=self.CABLE, CABLE_PORT=value)

    @pytest.mark.parametrize("value", ["cable", "", None])
    def test_the_path(self, value):
        with pytest.raises(ConfigError, match="CABLE_PATH"):
            _app(CABLE=self.CABLE, CABLE_PATH=value)

    def test_the_slow_client_settings(self):
        _app(CABLE=self.CABLE, CABLE_MAX_PENDING_BYTES=0, CABLE_STALL_TIMEOUT=0.5)
        with pytest.raises(ConfigError, match="CABLE_MAX_PENDING_BYTES"):
            _app(CABLE=self.CABLE, CABLE_MAX_PENDING_BYTES=-1)
        for value in (0, "10", True):
            with pytest.raises(ConfigError, match="CABLE_STALL_TIMEOUT"):
                _app(CABLE=self.CABLE, CABLE_STALL_TIMEOUT=value)

    def test_a_cable_class_without_bind(self):
        class Plain(BaseCable):
            pass

        assert type(_app(CABLE={"type": Plain}).cable) is Plain

    def test_nothing_is_checked_without_a_cable(self):
        _app(CABLE={}, CABLE_PING_INTERVAL=0, CABLE_PATH="x")
