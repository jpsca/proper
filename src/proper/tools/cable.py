from ..cable import Cable
from ..errors import ConfigError
from ..helpers.imports import get_instance


NAME = "CHANNELS"
DEFAULT_CONFIG = {}


def setup(app):
    config = app.config.get(NAME, DEFAULT_CONFIG)
    if not config:
        app.cable = Cable()
        return

    validate_config(config)
    app.config[NAME] = config
    app.cable = get_instance(**config)


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError(f"{NAME} config must be a dictionary")

    if "type" not in config:
        raise ConfigError(f"{NAME} config must have a 'type' key")
    if not isinstance(config["type"], (str | type)):
        raise ConfigError(f"{NAME}['type'] must be a string or a class")
