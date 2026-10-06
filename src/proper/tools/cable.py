from ..channels import BaseCable
from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "CABLE"
DEFAULT_CONFIG = {}


def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    if not config:
        if app.config.get("CABLE_PORT"):
            raise ConfigError(
                f"CABLE_PORT is set but {NAME} is empty, and the default cable serves no "
                f'WebSockets. Set {NAME} = {{"type": "proper.channels.Cable"}} '
                '(and `uv add proper-wse`), or remove CABLE_PORT.'
            )
        # No channels: a cable with no WebSockets, where broadcasts reach no one.
        app.cable = BaseCable()
        return

    validate_config(config)
    app.config[NAME] = config
    app.cable = get_instance(**config)
    # A backend that serves the WebSockets itself (Cable) needs the app,
    # to run the channels.
    if hasattr(app.cable, "bind"):
        app.cable.bind(app)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")
